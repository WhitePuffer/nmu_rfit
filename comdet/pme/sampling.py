from __future__ import absolute_import
import numpy as np
import scipy.spatial.distance as distance
import itertools


class UniformSampler(object):
    def __init__(self, n_samples=None):
        self.n_samples = n_samples

    def generate(self, x, min_sample_size):
        n_elements = x.shape[0]
        for i in range(self.n_samples):
            while True:
                sample = np.random.randint(0, n_elements, size=min_sample_size)
                if np.unique(sample).size == min_sample_size:
                    break
            yield sample


class GaussianLocalSampler(object):
    def __init__(self, sigma, n_samples=None):
        self.n_samples = n_samples
        # p(x[i] | x[j]) = exp(-(dist(x[i], x[j])) / sigma)
        self.var = sigma ** 2
        self.distribution = None

    def generate(self, x, min_sample_size):
        n_elements = x.shape[0]
        self.distribution = np.zeros((n_elements,))
        counter_samples = 0
        counter_total = 0
        while (counter_samples < self.n_samples and
                       counter_total < self.n_samples * 100):
            bins = np.cumsum(self.distribution.max() - self.distribution)
            bins /= bins[-1]
            rnd = np.random.random()
            j = np.searchsorted(bins, rnd)
            dists = distance.cdist(x, np.atleast_2d(x[j, :]), 'euclidean')
            bins = np.cumsum(np.exp(-(dists ** 2) / self.var))
            bins /= bins[-1]

            success = False
            for _ in range(100):
                rnd = np.random.random((min_sample_size - 1,))
                sample = np.searchsorted(bins, rnd)
                sample = np.hstack((sample, [j]))
                if np.unique(sample).size == min_sample_size:
                    success = True
                    break

            if success:
                self.distribution[sample] += 1
                counter_samples += 1
                yield sample
            counter_total += 1


def model_generator(model_class, elements, sampler):
    samples = sampler.generate(elements, model_class().min_sample_size)
    for s in samples:
        ms_set = np.take(elements, s, axis=0)
        model = model_class()
        model.fit(ms_set)
        yield model


def inliers(model, elements, threshold):
    return model.distances(elements) <= threshold


def inliers_generator(mg, elements, threshold):
    return itertools.imap(lambda m: (m, inliers(m, elements, threshold)), mg)


def ransac_generator(model_class, elements, sampler, inliers_threshold):
    mg = model_generator(model_class, elements, sampler)
    return inliers_generator(mg, elements, inliers_threshold)


# if __name__ == '__main__':
#     x = np.random.rand(100, 2)
#     sampler = GaussianLocalSampler(0.1)
#     list(sampler.generate(x, 1, 2))
