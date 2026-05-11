"""
EPL Learn Package - Python Backend
Scikit-learn powered machine learning for EPL.
"""

import joblib
import numpy as np
from sklearn import datasets, feature_selection, metrics, model_selection, preprocessing
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

# ═══════════════════════════════════════════════════════════
#  Preprocessing
# ═══════════════════════════════════════════════════════════


def standard_scale(data):
    """Standardize features."""
    scaler = preprocessing.StandardScaler()
    return scaler.fit_transform(np.asarray(data)).tolist()


def minmax_scale(data):
    """Min-max scale to [0, 1]."""
    scaler = preprocessing.MinMaxScaler()
    return scaler.fit_transform(np.asarray(data)).tolist()


def label_encode(labels):
    """Encode labels as integers."""
    encoder = preprocessing.LabelEncoder()
    return encoder.fit_transform(labels).tolist()


def one_hot_encode(labels):
    """One-hot encode labels."""
    encoder = preprocessing.OneHotEncoder(sparse_output=False)
    return encoder.fit_transform(np.asarray(labels).reshape(-1, 1)).tolist()


def train_test_split(X, y, test_size=0.2):
    """Split data into train/test sets."""
    X_train, X_test, y_train, y_test = model_selection.train_test_split(
        np.asarray(X), np.asarray(y), test_size=test_size, random_state=42
    )
    return {
        'X_train': X_train.tolist(),
        'X_test': X_test.tolist(),
        'y_train': y_train.tolist(),
        'y_test': y_test.tolist(),
    }


def impute(data, strategy='mean'):
    """Fill missing values."""
    imputer = SimpleImputer(strategy=strategy)
    return imputer.fit_transform(np.asarray(data)).tolist()


def pca(data, n_components):
    """PCA dimensionality reduction."""
    reducer = PCA(n_components=n_components)
    return reducer.fit_transform(np.asarray(data)).tolist()


# ═══════════════════════════════════════════════════════════
#  Classification Models
# ═══════════════════════════════════════════════════════════


def create_logistic():
    """Create logistic regression."""
    return LogisticRegression(max_iter=1000)


def create_tree_classifier(max_depth=None):
    """Create decision tree classifier."""
    return DecisionTreeClassifier(max_depth=max_depth)


def create_rf_classifier(n_estimators=100, max_depth=None):
    """Create random forest classifier."""
    return RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth)


def create_svm(kernel='rbf'):
    """Create SVM classifier."""
    return SVC(kernel=kernel, probability=True)


def create_knn_classifier(n_neighbors=5):
    """Create KNN classifier."""
    return KNeighborsClassifier(n_neighbors=n_neighbors)


def create_naive_bayes():
    """Create Gaussian Naive Bayes."""
    return GaussianNB()


def create_gb_classifier(n_estimators=100, learning_rate=0.1):
    """Create gradient boosting classifier."""
    return GradientBoostingClassifier(n_estimators=n_estimators, learning_rate=learning_rate)


# ═══════════════════════════════════════════════════════════
#  Regression Models
# ═══════════════════════════════════════════════════════════


def create_linear():
    """Create linear regression."""
    return LinearRegression()


def create_ridge(alpha=1.0):
    """Create ridge regression."""
    return Ridge(alpha=alpha)


def create_lasso(alpha=1.0):
    """Create lasso regression."""
    return Lasso(alpha=alpha)


def create_tree_regressor(max_depth=None):
    """Create decision tree regressor."""
    return DecisionTreeRegressor(max_depth=max_depth)


def create_rf_regressor(n_estimators=100, max_depth=None):
    """Create random forest regressor."""
    return RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth)


def create_svr(kernel='rbf'):
    """Create support vector regressor."""
    return SVR(kernel=kernel)


def create_knn_regressor(n_neighbors=5):
    """Create KNN regressor."""
    return KNeighborsRegressor(n_neighbors=n_neighbors)


# ═══════════════════════════════════════════════════════════
#  Training & Prediction
# ═══════════════════════════════════════════════════════════


def fit(model, X, y):
    """Train model."""
    model.fit(np.asarray(X), np.asarray(y))
    return model


def predict(model, X):
    """Make predictions."""
    return model.predict(np.asarray(X)).tolist()


def predict_proba(model, X):
    """Get prediction probabilities."""
    return model.predict_proba(np.asarray(X)).tolist()


# ═══════════════════════════════════════════════════════════
#  Clustering
# ═══════════════════════════════════════════════════════════


def kmeans(data, n_clusters):
    """K-means clustering."""
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    model.fit(np.asarray(data))
    return model


def dbscan(data, eps=0.5, min_samples=5):
    """DBSCAN clustering."""
    model = DBSCAN(eps=eps, min_samples=min_samples)
    model.fit(np.asarray(data))
    return model


def agglomerative(data, n_clusters):
    """Agglomerative clustering."""
    model = AgglomerativeClustering(n_clusters=n_clusters)
    model.fit(np.asarray(data))
    return model


def get_labels(model):
    """Get cluster labels."""
    return model.labels_.tolist()


def get_centers(model):
    """Get cluster centers."""
    return model.cluster_centers_.tolist() if hasattr(model, 'cluster_centers_') else []


# ═══════════════════════════════════════════════════════════
#  Evaluation - Classification
# ═══════════════════════════════════════════════════════════


def accuracy(y_true, y_pred):
    """Accuracy score."""
    return metrics.accuracy_score(np.asarray(y_true), np.asarray(y_pred))


def precision(y_true, y_pred):
    """Precision score."""
    return metrics.precision_score(np.asarray(y_true), np.asarray(y_pred), average='weighted')


def recall(y_true, y_pred):
    """Recall score."""
    return metrics.recall_score(np.asarray(y_true), np.asarray(y_pred), average='weighted')


def f1(y_true, y_pred):
    """F1 score."""
    return metrics.f1_score(np.asarray(y_true), np.asarray(y_pred), average='weighted')


def confusion_matrix(y_true, y_pred):
    """Confusion matrix."""
    return metrics.confusion_matrix(np.asarray(y_true), np.asarray(y_pred)).tolist()


def classification_report(y_true, y_pred):
    """Classification report."""
    return metrics.classification_report(np.asarray(y_true), np.asarray(y_pred))


def roc_auc(y_true, y_scores):
    """ROC AUC score."""
    return metrics.roc_auc_score(np.asarray(y_true), np.asarray(y_scores))


# ═══════════════════════════════════════════════════════════
#  Evaluation - Regression
# ═══════════════════════════════════════════════════════════


def mse(y_true, y_pred):
    """Mean squared error."""
    return metrics.mean_squared_error(np.asarray(y_true), np.asarray(y_pred))


def rmse(y_true, y_pred):
    """Root mean squared error."""
    return np.sqrt(metrics.mean_squared_error(np.asarray(y_true), np.asarray(y_pred)))


def mae(y_true, y_pred):
    """Mean absolute error."""
    return metrics.mean_absolute_error(np.asarray(y_true), np.asarray(y_pred))


def r2(y_true, y_pred):
    """R² score."""
    return metrics.r2_score(np.asarray(y_true), np.asarray(y_pred))


# ═══════════════════════════════════════════════════════════
#  Cross-Validation
# ═══════════════════════════════════════════════════════════


def cross_val_score(model, X, y, cv=5):
    """Cross-validation scores."""
    scores = model_selection.cross_val_score(model, np.asarray(X), np.asarray(y), cv=cv)
    return {'scores': scores.tolist(), 'mean': scores.mean(), 'std': scores.std()}


def grid_search(model, X, y, param_grid, cv=5):
    """Grid search hyperparameter tuning."""
    search = model_selection.GridSearchCV(model, param_grid, cv=cv)
    search.fit(np.asarray(X), np.asarray(y))
    return {'best_params': search.best_params_, 'best_score': search.best_score_}


# ═══════════════════════════════════════════════════════════
#  Feature Selection
# ═══════════════════════════════════════════════════════════


def select_k_best(X, y, k):
    """Select k best features."""
    selector = feature_selection.SelectKBest(k=k)
    X_new = selector.fit_transform(np.asarray(X), np.asarray(y))
    return {
        'data': X_new.tolist(),
        'scores': selector.scores_.tolist(),
        'selected_indices': selector.get_support(indices=True).tolist(),
    }


def feature_importance(model):
    """Get feature importances."""
    if hasattr(model, 'feature_importances_'):
        return model.feature_importances_.tolist()
    return []


# ═══════════════════════════════════════════════════════════
#  Model Persistence
# ═══════════════════════════════════════════════════════════


def save_model(model, filepath):
    """Save model to file."""
    joblib.dump(model, filepath)
    return f'Model saved to {filepath}'


def load_model(filepath):
    """Load model from file."""
    return joblib.load(filepath)


# ═══════════════════════════════════════════════════════════
#  Built-in Datasets
# ═══════════════════════════════════════════════════════════


def load_iris():
    """Load Iris dataset."""
    data = datasets.load_iris()
    return {
        'X': data.data.tolist(),
        'y': data.target.tolist(),
        'feature_names': data.feature_names.tolist(),
    }


def load_digits():
    """Load Digits dataset."""
    data = datasets.load_digits()
    return {'X': data.data.tolist(), 'y': data.target.tolist()}


def load_boston():
    """Load Boston housing (deprecated, use California housing)."""
    try:
        data = datasets.load_boston()
        return {'X': data.data.tolist(), 'y': data.target.tolist()}
    except:
        data = datasets.fetch_california_housing()
        return {'X': data.data.tolist(), 'y': data.target.tolist()}


def load_wine():
    """Load Wine dataset."""
    data = datasets.load_wine()
    return {
        'X': data.data.tolist(),
        'y': data.target.tolist(),
        'feature_names': data.feature_names.tolist(),
    }


def make_classification(n_samples=100, n_features=20, n_classes=2):
    """Generate classification data."""
    X, y = datasets.make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_classes=n_classes,
        n_informative=n_features // 2,
        random_state=42,
    )
    return {'X': X.tolist(), 'y': y.tolist()}


def make_regression(n_samples=100, n_features=10):
    """Generate regression data."""
    X, y = datasets.make_regression(n_samples=n_samples, n_features=n_features, random_state=42)
    return {'X': X.tolist(), 'y': y.tolist()}


def make_blobs(n_samples=100, n_centers=3):
    """Generate blob data for clustering."""
    X, y = datasets.make_blobs(n_samples=n_samples, centers=n_centers, random_state=42)
    return {'X': X.tolist(), 'y': y.tolist()}
