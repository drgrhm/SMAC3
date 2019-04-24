import math

import numpy as np
import scipy.stats as sps
import scipy.special as scsp

from smac.utils.constants import VERY_SMALL_NUMBER


class Prior(object):

    def __init__(self, rng: np.random.RandomState=None):
        """
        Abstract base class to define the interface for priors
        of GP hyperparameter.

        This class is a verbatim copy of the implementation of RoBO:

        Klein, A. and Falkner, S. and Mansur, N. and Hutter, F.
        RoBO: A Flexible and Robust Bayesian Optimization Framework in Python
        In: NIPS 2017 Bayesian Optimization Workshop

        [16.04.2019]: Whenever lnprob or the gradient is computed for a scalar input, we use math.* rather than np.*

        Parameters
        ----------
        rng: np.random.RandomState
            Random number generator

        """
        if rng is None:
            self.rng = np.random.RandomState(np.random.randint(0, 10000))
        else:
            self.rng = rng

    def lnprob(self, theta: np.ndarray):
        """
        Returns the log probability of theta. Note: theta should
        be on a log scale.

        Parameters
        ----------
        theta : (D,) numpy array
            A hyperparameter configuration in log space.

        Returns
        -------
        float
            The log probability of theta
        """
        return self._lnprob(np.exp(theta))

    def _lnprob(self, theta: np.ndarray):
        raise NotImplementedError()

    def sample_from_prior(self, n_samples: int):
        """
        Returns N samples from the prior (already on a logscale)

        Parameters
        ----------
        n_samples : int
            The number of samples that will be drawn.

        Returns
        -------
        (N, D) np.array
            The samples from the prior.
        """

        if np.ndim(n_samples) != 0:
            raise ValueError('argument n_samples needs to be a scalar (is %s)' % n_samples)
        if n_samples <= 0:
            raise ValueError('argument n_samples needs to be positive (is %d)' % n_samples)

        return np.log(self._sample_from_prior(n_samples=n_samples))

    def _sample_from_prior(self, n_samples: int):
        raise NotImplementedError()

    def gradient(self, theta: np.ndarray):
        """
        Computes the gradient of the prior with
        respect to theta.

        Parameters
        ----------
        theta : (D,) numpy array
            Hyperparameter configuration in log space

        Returns
        -------
        (D) np.array
            The gradient of the prior at theta.
        """
        return self._gradient(np.exp(theta))

    def _gradient(self, theta: np.ndarray):
        raise NotImplementedError()


class TophatPrior(Prior):

    def __init__(self, lower_bound: float, upper_bound: float, rng: np.random.RandomState=None):
        """
        Tophat prior as it used in the original spearmint code.

        This class is a verbatim copy of the implementation of RoBO:

        Klein, A. and Falkner, S. and Mansur, N. and Hutter, F.
        RoBO: A Flexible and Robust Bayesian Optimization Framework in Python
        In: NIPS 2017 Bayesian Optimization Workshop

        [19.04.2019]: Don't log samples afterwards or exponentiate theta before

        Parameters
        ----------
        lower_bound : float
            Lower bound of the prior. In original scale.
        upper_bound : float
            Upper bound of the prior. In original scale.
        rng: np.random.RandomState
            Random number generator
        """
        if rng is None:
            self.rng = np.random.RandomState(np.random.randint(0, 10000))
        else:
            self.rng = rng
        self.min = lower_bound
        self.max = upper_bound
        if not (self.max > self.min):
            raise Exception("Upper bound of Tophat prior must be greater than the lower bound!")

    def lnprob(self, theta: np.ndarray):
        """
        Returns the log probability of theta.

        Parameters
        ----------
        theta : (D,) numpy array
            A hyperparameter configuration

        Returns
        -------
        float
            The log probability of theta
        """
        if np.ndim(theta) == 0:
            if theta < self.min or theta > self.max:
                return -np.inf
            else:
                return 0
        else:
            raise NotImplementedError()

    def sample_from_prior(self, n_samples: int):
        """
        Returns N samples from the prior.


        Parameters
        ----------
        n_samples : int
            The number of samples that will be drawn.

        Returns
        -------
        (N, D) np.array
            The samples from the prior.
        """

        if np.ndim(n_samples) != 0:
            raise ValueError('argument n_samples needs to be a scalar (is %s)' % n_samples)
        if n_samples <= 0:
            raise ValueError('argument n_samples needs to be positive (is %d)' % n_samples)

        p0 = self.min + self.rng.rand(n_samples) * (self.max - self.min)
        return p0

    def gradient(self, theta: np.ndarray):
        """
        Computes the gradient of the prior with
        respect to theta.

        Parameters
        ----------
        theta : (D,) numpy array
            Hyperparameter configuration in log space

        Returns
        -------
        (D) np.array

            The gradient of the prior at theta.
        """
        if np.ndim(theta) == 0:
            return 0
        else:
            raise NotImplementedError()


class HorseshoePrior(Prior):

    def __init__(self, scale: float=0.1, rng: np.random.RandomState=None):
        """
        Horseshoe Prior as it is used in spearmint

        This class is a verbatim copy of the implementation of RoBO:

        Klein, A. and Falkner, S. and Mansur, N. and Hutter, F.
        RoBO: A Flexible and Robust Bayesian Optimization Framework in Python
        In: NIPS 2017 Bayesian Optimization Workshop

        Parameters
        ----------
        scale: float
            Scaling parameter. See below how it is influencing the distribution.
        rng: np.random.RandomState
            Random number generator
        """
        if rng is None:
            self.rng = np.random.RandomState(np.random.randint(0, 10000))
        else:
            self.rng = rng
        self.scale = scale
        self.scale_square = scale ** 2

    def _lnprob(self, theta: np.ndarray):
        """
        Returns the log probability of theta.

        Parameters
        ----------
        theta : (D,) numpy array
            A hyperparameter configuration

        Returns
        -------
        float
            The log probability of theta
        """
        # We computed it exactly as in the original spearmint code, they basically say that there's no analytical form
        # of the horseshoe prior, but that the multiplier is bounded between 2 and 4 and that they used the middle
        # See "The horseshoe estimator for sparse signals" by Carvalho, Poloson and Scott (2010), Equation 1.
        # https://www.jstor.org/stable/25734098
        # Compared to the paper by Carvalho, there's a constant multiplicator missing
        # Compared to Spearmint we first have to undo the log space transformation of the theta
        # Note: "undo log space transformation" is done in parent class
        if np.ndim(theta) == 0:
            if theta == 0:
                return np.inf  # POSITIVE infinity (this is the "spike")
        else:
            raise NotImplementedError()

        a = math.log(1 + 3.0 * (self.scale_square / theta**2))
        return math.log(a + VERY_SMALL_NUMBER)

    def _sample_from_prior(self, n_samples: int):
        """
        Returns N samples from the prior.

        Parameters
        ----------
        n_samples : int
            The number of samples that will be drawn.

        Returns
        -------
        (N, D) np.array
            The samples from the prior.
        """

        lamda = np.abs(self.rng.standard_cauchy(size=n_samples))

        #p0 = np.log(np.abs(self.rng.randn() * lamda * self.scale))
        p0 = np.abs(self.rng.randn() * lamda * self.scale)
        return p0

    def _gradient(self, theta: np.ndarray):
        """
        Computes the gradient of the prior with
        respect to theta.

        Parameters
        ----------
        theta : (D,) numpy array
            Hyperparameter configuration

        Returns
        -------
        (D) np.array
            The gradient of the prior at theta.
        """
        if np.ndim(theta) == 0:
            if theta == 0:
                return np.inf  # POSITIVE infinity (this is the "spike")
            else:
                a = -(6 * self.scale_square)
                #b = (3 * self.scale_square + math.exp(2 * theta))
                b = 3 * self.scale_square + theta**2
                #b *= math.log(3 * self.scale_square * math.exp(- 2 * theta) + 1)
                b *= math.log(3 * self.scale_square * theta ** (-2) + 1)
                b = max(b, 1e-14)
                return a / b

        else:
            raise NotImplementedError()


class LognormalPrior(Prior):

    def __init__(self, sigma: float, mean: float=0, rng: np.random.RandomState=None):
        """
        Log normal prior

        This class is a verbatim copy of the implementation of RoBO:

        Klein, A. and Falkner, S. and Mansur, N. and Hutter, F.
        RoBO: A Flexible and Robust Bayesian Optimization Framework in Python
        In: NIPS 2017 Bayesian Optimization Workshop

        Parameters
        ----------
        sigma: float
            Specifies the standard deviation of the normal
            distribution.
        mean: float
            Specifies the mean of the normal distribution
        rng: np.random.RandomState
            Random number generator
        """
        if rng is None:
            self.rng = np.random.RandomState(np.random.randint(0, 10000))
        else:
            self.rng = rng

        if mean != 0:
            raise NotImplementedError(mean)

        self.sigma = sigma
        self.sigma_square = sigma ** 2
        self.mean = mean
        self.sqrt_2_pi = np.sqrt(2 * np.pi)

    def _lnprob(self, theta: np.ndarray):
        """
        Returns the log probability of theta

        Parameters
        ----------
        theta : (D,) numpy array
            A hyperparameter configuration

        Returns
        -------
        float
            The log probability of theta
        """
        if np.ndim(theta) == 0:
            if theta <= self.mean:
                return -1e25
            else:
                rval = (
                    -(math.log(theta) - self.mean) ** 2 / (2 * self.sigma_square)
                    - math.log(self.sqrt_2_pi * self.sigma * theta)
                )
                return rval

        else:
            raise NotImplementedError()

    def _sample_from_prior(self, n_samples: int):
        """
        Returns N samples from the prior.

        Parameters
        ----------
        n_samples : int
            The number of samples that will be drawn.

        Returns
        -------
        (N, D) np.array
            The samples from the prior.
        """

        p0 = self.rng.lognormal(mean=self.mean, sigma=self.sigma, size=n_samples)
        return p0

    def _gradient(self, theta: np.ndarray):
        """
        Computes the gradient of the prior with
        respect to theta.

        Parameters
        ----------
        theta : (D,) numpy array
            Hyperparameter configuration in log space

        Returns
        -------
        (D) np.array
            The gradient of the prior at theta.
        """
        if np.ndim(theta) == 0:
            if theta <= 0:
                return 0
            else:
                # derivative of log(1 / (x * s^2 * sqrt(2 pi)) * exp( - 0.5 * (log(x ) / s^2))^2))
                # This is without the mean!!!
                return -(self.sigma_square + math.log(theta)) / (self.sigma_square * (theta)) * theta

        else:
            raise NotImplementedError()


class SoftTopHatPrior(Prior):
    def __init__(self, lower_bound=-10, upper_bound=10, exponent=2, rng: np.random.RandomState=None):
        super().__init__(rng=rng)
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        if exponent <= 0:
            raise ValueError('Exponent cannot be less or equal than zero (but is %f)' % exponent)
        self.exponent = exponent

    def _lnprob(self, theta: np.ndarray):
        if np.ndim(theta) == 0 or (np.ndim(theta) == 1 and len(theta) == 1):
            if theta < self.lower_bound:
                return - ((theta - self.lower_bound) ** self.exponent)
            elif theta > self.upper_bound:
                return - (self.upper_bound - theta) ** self.exponent
            else:
                return 0
        else:
            raise NotImplementedError()

    def _sample_from_prior(self, n_samples: int):
        """
        Returns N samples from the prior.

        Parameters
        ----------
        n_samples : int
            The number of samples that will be drawn.

        Returns
        -------
        (N, D) np.array
            The samples from the prior.
        """

        return self.rng.uniform(self.lower_bound, self.upper_bound, size=(n_samples, ))

    def _gradient(self, theta: np.ndarray):
        if np.ndim(theta) == 0 or (np.ndim(theta) == 1 and len(theta) == 1):
            if theta < self.lower_bound:
                return - self.exponent * (theta - self.lower_bound)
            elif theta > self.upper_bound:
                return self.exponent * ( self.upper_bound - theta)
            else:
                return 0
        else:
            raise NotImplementedError()

    def __str__(self):
        return 'LowerBoundPrior(lower_bound=%f)' % self.lower_bound


class GammaPrior(Prior):

    def __init__(self, a: float, scale: float, loc: float=0, rng: np.random.RandomState=None):
        """
        Gamma prior

        f(x) = (x-loc)**(a-1) * e**(-(x-loc)) * (1/scale)**a / gamma(a)

        Parameters
        ----------
        a: float > 0
            shape parameter
        scale: float > 0
            scale parameter (1/scale corresponds to parameter p in canonical form)
        loc: float
            mean parameter for the distribution
        rng: np.random.RandomState
            Random number generator
        """
        super().__init__(rng=rng)

        self.a = a
        self.loc = loc
        self.scale = scale

    def _lnprob(self, theta: np.ndarray):
        """
        Returns the pdf of theta.

        Parameters
        ----------
        theta : (D,) numpy array
            A hyperparameter configuration

        Returns
        -------
        float
            The log probability of theta
        """
        if np.ndim(theta) != 0:
            raise NotImplementedError()
        return sps.gamma.logpdf(theta, a=self.a, scale=self.scale, loc=self.loc)

    def _sample_from_prior(self, n_samples: int):
        """
        Returns N samples from the prior.

        Parameters
        ----------
        n_samples : int
            The number of samples that will be drawn.

        Returns
        -------
        (N, D) np.array
            The samples from the prior.
        """

        p0 = self.rng.gamma(shape=self.a, scale=self.scale, size=n_samples)
        return p0

    def _gradient(self, theta: np.ndarray):
        """
        As computed by Wolfram Alpha

        Parameters
        ----------
        theta: (D,) numpy array
            A hyperparameter configuration

        Returns
        -------
        float
            The gradient wrt to theta
        """
        if np.ndim(theta) == 0:
            # Multiply by theta because of the chain rule...
            return ((self.a - 1) / theta - (1 / self.scale)) * theta
        else:
            raise NotImplementedError()
