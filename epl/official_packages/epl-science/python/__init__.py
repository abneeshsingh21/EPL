"""
EPL Science Package - Python Backend
SciPy-powered scientific computing for EPL.
"""

import numpy as np
from scipy import integrate, interpolate, optimize, signal, special, stats
from scipy.spatial import distance

# ═══════════════════════════════════════════════════════════
#  Optimization
# ═══════════════════════════════════════════════════════════


def minimize(func, x0, method='BFGS'):
    """Minimize a function."""
    result = optimize.minimize(func, x0, method=method)
    return {'x': result.x.tolist(), 'fun': result.fun, 'success': result.success}


def maximize(func, x0, method='BFGS'):
    """Maximize a function (minimize -f)."""
    neg_func = lambda x: -func(x)
    result = optimize.minimize(neg_func, x0, method=method)
    return {'x': result.x.tolist(), 'fun': -result.fun, 'success': result.success}


def find_root(func, x0):
    """Find root of a scalar function."""
    result = optimize.root_scalar(
        func, x0=x0, method='brentq' if hasattr(func, '__call__') else 'newton'
    )
    return result.root


def find_roots(func, bracket):
    """Find roots in a bracket."""
    result = optimize.brentq(func, bracket[0], bracket[1])
    return result


def solve_equation(func, x0):
    """Solve system of equations."""
    result = optimize.fsolve(func, x0)
    return result.tolist()


def lstsq(A, b):
    """Least squares solution."""
    result = np.linalg.lstsq(np.asarray(A), np.asarray(b), rcond=None)
    return {
        'solution': result[0].tolist(),
        'residuals': result[1].tolist() if len(result[1]) > 0 else [],
    }


def curve_fit(func, xdata, ydata):
    """Fit curve to data."""
    popt, pcov = optimize.curve_fit(func, np.asarray(xdata), np.asarray(ydata))
    return {'params': popt.tolist(), 'covariance': pcov.tolist()}


# ═══════════════════════════════════════════════════════════
#  Integration
# ═══════════════════════════════════════════════════════════


def integrate_func(func, a, b):
    """Definite integral."""
    result, error = integrate.quad(func, a, b)
    return {'value': result, 'error': error}


def trapezoid(y, x=None):
    """Trapezoidal integration."""
    return integrate.trapezoid(np.asarray(y), np.asarray(x) if x else None)


def simpson(y, x=None):
    """Simpson's rule integration."""
    return integrate.simpson(np.asarray(y), x=np.asarray(x) if x else None)


def dblquad(func, x_range, y_range):
    """Double integral."""
    result, error = integrate.dblquad(
        func, x_range[0], x_range[1], lambda x: y_range[0], lambda x: y_range[1]
    )
    return {'value': result, 'error': error}


def solve_ivp(func, y0, t_span, t_eval=None):
    """Solve ODE initial value problem."""
    if t_eval is None:
        t_eval = np.linspace(t_span[0], t_span[1], 100)
    result = integrate.solve_ivp(func, t_span, y0, t_eval=t_eval)
    return {'t': result.t.tolist(), 'y': result.y.tolist()}


# ═══════════════════════════════════════════════════════════
#  Interpolation
# ═══════════════════════════════════════════════════════════


def interp_linear(x_points, y_points):
    """Linear interpolation."""
    return interpolate.interp1d(np.asarray(x_points), np.asarray(y_points), kind='linear')


def interp_cubic(x_points, y_points):
    """Cubic interpolation."""
    return interpolate.interp1d(np.asarray(x_points), np.asarray(y_points), kind='cubic')


def interp_eval(interp_func, x):
    """Evaluate interpolation."""
    return interp_func(x).tolist() if hasattr(x, '__len__') else float(interp_func(x))


def spline_fit(x_points, y_points, smoothing=0):
    """Smoothing spline."""
    return interpolate.UnivariateSpline(np.asarray(x_points), np.asarray(y_points), s=smoothing)


# ═══════════════════════════════════════════════════════════
#  Signal Processing
# ═══════════════════════════════════════════════════════════


def fft(sig):
    """Fast Fourier Transform."""
    return np.fft.fft(np.asarray(sig)).tolist()


def ifft(spectrum):
    """Inverse FFT."""
    return np.fft.ifft(np.asarray(spectrum)).tolist()


def freq_spectrum(sig, sample_rate):
    """Frequency spectrum."""
    sig = np.asarray(sig)
    n = len(sig)
    freqs = np.fft.fftfreq(n, 1 / sample_rate)
    spectrum = np.abs(np.fft.fft(sig))
    return {'frequencies': freqs[: n // 2].tolist(), 'magnitudes': spectrum[: n // 2].tolist()}


def convolve(sig1, sig2):
    """Convolve signals."""
    return signal.convolve(np.asarray(sig1), np.asarray(sig2)).tolist()


def correlate(sig1, sig2):
    """Cross-correlate signals."""
    return signal.correlate(np.asarray(sig1), np.asarray(sig2)).tolist()


def filter_signal(sig, filter_type, cutoff, sample_rate, order=5):
    """Apply Butterworth filter."""
    nyquist = sample_rate / 2
    normalized_cutoff = cutoff / nyquist
    b, a = signal.butter(order, normalized_cutoff, btype=filter_type)
    return signal.filtfilt(b, a, np.asarray(sig)).tolist()


def find_peaks_func(sig, height=None, distance=None):
    """Find peaks in signal."""
    peaks, properties = signal.find_peaks(np.asarray(sig), height=height, distance=distance)
    return {'indices': peaks.tolist(), 'heights': properties.get('peak_heights', []).tolist()}


def smooth(sig, window_size):
    """Moving average smoothing."""
    return np.convolve(np.asarray(sig), np.ones(window_size) / window_size, mode='valid').tolist()


# ═══════════════════════════════════════════════════════════
#  Statistical Tests
# ═══════════════════════════════════════════════════════════


def ttest(sample1, sample2):
    """Two-sample t-test."""
    stat, pvalue = stats.ttest_ind(np.asarray(sample1), np.asarray(sample2))
    return {'statistic': stat, 'pvalue': pvalue}


def ttest_1samp(sample, popmean):
    """One-sample t-test."""
    stat, pvalue = stats.ttest_1samp(np.asarray(sample), popmean)
    return {'statistic': stat, 'pvalue': pvalue}


def ttest_paired(sample1, sample2):
    """Paired t-test."""
    stat, pvalue = stats.ttest_rel(np.asarray(sample1), np.asarray(sample2))
    return {'statistic': stat, 'pvalue': pvalue}


def chisquare(observed, expected=None):
    """Chi-square test."""
    stat, pvalue = stats.chisquare(np.asarray(observed), np.asarray(expected) if expected else None)
    return {'statistic': stat, 'pvalue': pvalue}


def anova(groups):
    """One-way ANOVA."""
    stat, pvalue = stats.f_oneway(*[np.asarray(g) for g in groups])
    return {'statistic': stat, 'pvalue': pvalue}


def pearsonr(x, y):
    """Pearson correlation."""
    r, pvalue = stats.pearsonr(np.asarray(x), np.asarray(y))
    return {'correlation': r, 'pvalue': pvalue}


def spearmanr(x, y):
    """Spearman correlation."""
    r, pvalue = stats.spearmanr(np.asarray(x), np.asarray(y))
    return {'correlation': r, 'pvalue': pvalue}


def shapiro(data):
    """Shapiro-Wilk normality test."""
    stat, pvalue = stats.shapiro(np.asarray(data))
    return {'statistic': stat, 'pvalue': pvalue}


def kstest(data, distribution):
    """Kolmogorov-Smirnov test."""
    stat, pvalue = stats.kstest(np.asarray(data), distribution)
    return {'statistic': stat, 'pvalue': pvalue}


# ═══════════════════════════════════════════════════════════
#  Distributions
# ═══════════════════════════════════════════════════════════


def norm_pdf(x, mean=0, std=1):
    """Normal PDF."""
    return stats.norm.pdf(x, loc=mean, scale=std)


def norm_cdf(x, mean=0, std=1):
    """Normal CDF."""
    return stats.norm.cdf(x, loc=mean, scale=std)


def norm_rvs(mean=0, std=1, size=1):
    """Normal random samples."""
    return stats.norm.rvs(loc=mean, scale=std, size=size).tolist()


def uniform_rvs(low=0, high=1, size=1):
    """Uniform random samples."""
    return stats.uniform.rvs(loc=low, scale=high - low, size=size).tolist()


def expon_rvs(scale=1, size=1):
    """Exponential random samples."""
    return stats.expon.rvs(scale=scale, size=size).tolist()


def poisson_rvs(mu, size=1):
    """Poisson random samples."""
    return stats.poisson.rvs(mu=mu, size=size).tolist()


def binom_rvs(n, p, size=1):
    """Binomial random samples."""
    return stats.binom.rvs(n=n, p=p, size=size).tolist()


# ═══════════════════════════════════════════════════════════
#  Distance & Similarity
# ═══════════════════════════════════════════════════════════


def euclidean(a, b):
    """Euclidean distance."""
    return distance.euclidean(np.asarray(a), np.asarray(b))


def cosine(a, b):
    """Cosine similarity."""
    return 1 - distance.cosine(np.asarray(a), np.asarray(b))


def manhattan(a, b):
    """Manhattan distance."""
    return distance.cityblock(np.asarray(a), np.asarray(b))


def pdist_matrix(points):
    """Pairwise distance matrix."""
    return distance.squareform(distance.pdist(np.asarray(points))).tolist()


# ═══════════════════════════════════════════════════════════
#  Special Functions
# ═══════════════════════════════════════════════════════════


def gamma(x):
    """Gamma function."""
    return special.gamma(x)


def beta(a, b):
    """Beta function."""
    return special.beta(a, b)


def jn(n, x):
    """Bessel function of first kind."""
    return special.jn(n, x)


def erf(x):
    """Error function."""
    return special.erf(x)
