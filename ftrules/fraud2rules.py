"""
This is a module to be used as a reference for building other modules
"""
import numpy as np
import pandas  # XXX to be rm
import numbers
from warnings import warn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from sklearn.externals import six
from sklearn.tree import _tree

INTEGER_TYPES = (numbers.Integral, np.integer)


class FraudToRules(BaseEstimator, ClassifierMixin):
    """ An easy-interpretable classifier optimizing simple logical rules.

    Parameters
    ----------
    n_estimators : int, optional (default=1)
        The number of base estimators (rules) to build.

    feature_names: list of str, optional (default=None)
        XXX (remove it if we want generic tool)
        The names of each feature to be used for returning rules in string
        format.

    max_samples : int or float, optional (default=1.)
        The number of samples to draw from X to train each decision tree, from
        which rules are generated and selected.
            - If int, then draw `max_samples` samples.
            - If float, then draw `max_samples * X.shape[0]` samples.
        If max_samples is larger than the number of samples provided,
        all samples will be used for all trees (no sampling).

    max_features : int or float, optional (default=1.0)
        The number of features to draw from X to train each decision tree.
            - If int, then draw `max_features` features.
            - If float, then draw `max_features * X.shape[1]` features.

    max_depth : integer or None, optional (default=None)
        The maximum depth of the decision trees. If None, then nodes are
        expanded until all leaves are pure or until all leaves contain less
        than min_samples_split samples.  XXX faisable en pratique?

    min_samples_split : int, float, optional (default=2)
        The minimum number of samples required to split an internal node for
        each decision tree.
        - If int, then consider `min_samples_split` as the minimum number.
        - If float, then `min_samples_split` is a percentage and
          `ceil(min_samples_split * n_samples)` are the minimum
          number of samples for each split.

    XXX should we add more DecisionTree params?

    bootstrap : boolean, optional (default=False)
        If True, individual trees are fit on random subsets of the training
        data sampled with replacement. If False, sampling without replacement
        is performed.

    n_jobs : integer, optional (default=1)
        The number of jobs to run in parallel for both `fit` and `predict`.
        If -1, then the number of jobs is set to the number of cores.

    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.

    verbose : int, optional (default=0)
        Controls the verbosity of the tree building process.

    Attributes
    ----------
    rules_ : list of selected rules.
        The collection of rules generated by fitted sub-estimators (decision
        trees) and further selected according to their respective precisions.


    estimators_ : list of DecisionTreeClassifier
        The collection of fitted sub-estimators used to generate candidate
        rules.

    estimators_samples_ : list of arrays
        The subset of drawn samples (i.e., the in-bag samples) for each base
        estimator.

    max_samples_ : integer
        The actual number of samples
    """

    def __init__(self,
                 n_estimators=1,
                 feature_names=None,
                 max_samples=1.,
                 max_features=1.,
                 max_depth=None,
                 min_samples_split=2,
                 bootstrap=False,
                 n_jobs=1,
                 random_state=None,
                 verbose=0):
        self.n_estimators = n_estimators
        self.feature_names = feature_names
        self.max_samples = max_samples
        self.max_features = max_features
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.bootstrap = bootstrap
        self.n_jobs = n_jobs
        self.random_state = random_state
        self.verbose = verbose

    def fit(self, X, y, sample_weight=None):
        """Fit the model according to the given training data.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            Training vector, where n_samples is the number of samples and
            n_features is the number of features. XXX sparse matrix?

        y : array-like, shape (n_samples,)
            Target vector relative to X. Following convention bigger is better,
            frauds have to be labeled as -1, and normal data as 1.

        sample_weight : array-like, shape (n_samples,) optional
            Array of weights that are assigned to individual samples, typically
            the amount in case of transactions data. Used to grow regression
            trees producing further rules to be tested.
            If not provided, then each sample is given unit weight.

        Returns
        -------
        self : object
            Returns self.
        """

        X, y = check_X_y(X, y)

        testing_size = int(X.shape[0] / 10.)
        ind_test = range(X.shape[0])
        np.random.shuffle(ind_test)
        X_test = X[ind_test][:testing_size]
        X_train = X[ind_test][testing_size:]

        # ensure that max_samples is in [1, n_samples]:
        n_samples = X_train.shape[0]

        if isinstance(self.max_samples, six.string_types):
            raise ValueError('max_samples (%s) is not supported.'
                             'Valid choices are: "auto", int or'
                             'float' % self.max_samples)

        elif isinstance(self.max_samples, INTEGER_TYPES):
            if self.max_samples > n_samples:
                warn("max_samples (%s) is greater than the "
                     "total number of samples (%s). max_samples "
                     "will be set to n_samples for estimation."
                     % (self.max_samples, n_samples))
                max_samples = n_samples
            else:
                max_samples = self.max_samples
        else:  # float
            if not (0. < self.max_samples <= 1.):
                raise ValueError("max_samples must be in (0, 1], got %r"
                                 % self.max_samples)
            max_samples = int(self.max_samples * X_train.shape[0])

        self.max_samples_ = max_samples

        self.rules_ = []
        self.estimators_ = []

        for _ in range(self.n_estimators):
            # XXX TODO: use max_samples and bootstrap params
            clf = DecisionTreeClassifier(
                max_features=self.max_features,
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split)
            clf.fit(X_train, y)
            self.estimators_.append(clf)
            if self.feature_names is not None:
                rules = self._tree_to_rules(clf, self.feature_names)
            else:
                rules = self._tree_to_rules(clf,
                                            map(str, range(X_train.shape[1])))
            self.rules_ += rules

        # for _ in range(self.n_estimators):
        #     clf = DecisionTreeRegressor(
        #         max_features=self.max_features,
        #         max_depth=self.max_depth,
        #         min_samples_split=self.min_samples_split)
        #     clf.fit(X_train, y)
        #     self.estimators_.append(clf)
        #     if self.feature_names is not None:
        #         rules = self._tree_to_rules(clf, self.feature_names)
        #     else:
        #         rules = self._tree_to_rules(clf, map(str,
        #                                              range(X_train.shape[1])))
        #     self.rules_ += rules

        # XXX TODO: add to X_test the data not used in fit, in case of
        # subsampling or bootstrap.

        df = pandas.DataFrame(X_test, columns=self.feature_names)
        self.rules = [(r, df.query(r)) for r in self.rules_]
        self.rules_ = sorted(self.rules_, key=lambda x: -x[1])

        # XXX todo: create self.estimators_samples_

        # Return the classifier
        return self

    def predict(self, X):
        """Predict if a particular sample is an outlier or not.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            The input samples. Internally, it will be converted to
            ``dtype=np.float32`` XXX allow sparse matrix?

        Returns
        -------
        is_inlier : array, shape (n_samples,)
            For each observations, tells whether or not (+1 or -1) it should
            be considered as an inlier according to the fitted model.
        """

        # Check if fit had been called
        check_is_fitted(self, ['rules_', 'estimators_', 'estimators_samples_',
                               'max_samples_'])

        # Input validation
        X = check_array(X)

        return 2 * (self.decision_function(X) == 0) - 1

    def decision_function(self, X):
        """Average anomaly score of X of the base classifiers (rules).

        The anomaly score of an input sample is computed as
        the negative weighted sum of the binary rules outputs. The weight is
        the respective precision of each rule.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            The training input samples.

        Returns
        -------
        scores : array, shape (n_samples,)
            The anomaly score of the input samples.
            The lower, the more abnormal. Negative scores represent outliers,
            null scores represent inliers.

        """
        selected_rules = self.rules_[:self.n_estimators]
        df = pandas.DataFrame(X, columns=self.feature_names)

        scores = np.zeros(X.shape[0])
        for (r, w) in selected_rules:
            scores[list(df.query(r).index)] += w

        scores = -scores  # "bigger is better" convention (here less abnormal)
        return scores

    def _tree_to_rules(self, tree, feature_names):
        """
        Return a list of rules from a tree

        Parameters
        ----------
            tree : Decision Tree Classifier/Regressor
            feature_names: list of variable names

        Returns
        -------
        rules : list of rules.
        """
        # XXX todo: check the case where tree is build on subset of features,
        # ie max_features != None

        tree_ = tree.tree_
        feature_name = [
            feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
            for i in tree_.feature
        ]
        rules = []

        def recurse(node, base_name):
            if tree_.feature[node] != _tree.TREE_UNDEFINED:
                name = feature_name[node]
                symbol = '<='
                symbol2 = '>'
                threshold = tree_.threshold[node]
                text = base_name + ["{} {} {}".format(name, symbol, threshold)]
                recurse(tree_.children_left[node], text)

                text = base_name + ["{} {} {}".format(name, symbol2,
                                                      threshold)]
                recurse(tree_.children_right[node], text)
            else:
                rules.append(str.join(' and ', base_name))

        recurse(0, [])

        return rules
