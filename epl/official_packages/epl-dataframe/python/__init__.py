"""
EPL DataFrame Package - Python Backend
Pandas-powered data manipulation for EPL.
"""

import io

import pandas as pd

# ═══════════════════════════════════════════════════════════
#  DataFrame Creation
# ═══════════════════════════════════════════════════════════


def create_dataframe(data):
    """Create DataFrame from dict of columns."""
    return pd.DataFrame(data)


def from_lists(column_names, column_data):
    """Create DataFrame from column names and list of column data."""
    data = dict(zip(column_names, column_data))
    return pd.DataFrame(data)


def from_records(records):
    """Create DataFrame from list of dicts."""
    return pd.DataFrame.from_records(records)


def read_csv(filepath):
    """Read CSV file."""
    return pd.read_csv(filepath)


def read_json(filepath):
    """Read JSON file."""
    return pd.read_json(filepath)


def read_excel(filepath):
    """Read Excel file."""
    return pd.read_excel(filepath)


# ═══════════════════════════════════════════════════════════
#  DataFrame Properties
# ═══════════════════════════════════════════════════════════


def columns(df):
    """Get column names."""
    return list(df.columns)


def row_count(df):
    """Get number of rows."""
    return len(df)


def shape(df):
    """Get shape."""
    return df.shape


def dtypes(df):
    """Get data types."""
    return df.dtypes.to_dict()


def describe(df):
    """Get statistical summary."""
    return df.describe().to_dict()


def head(df, n=5):
    """Get first n rows."""
    return df.head(n)


def tail(df, n=5):
    """Get last n rows."""
    return df.tail(n)


def info(df):
    """Get DataFrame info."""
    buf = io.StringIO()
    df.info(buf=buf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════
#  Column Selection
# ═══════════════════════════════════════════════════════════


def select_column(df, column_name):
    """Select single column."""
    return df[column_name]


def select_columns(df, column_names):
    """Select multiple columns."""
    return df[column_names]


def drop_column(df, column_name):
    """Drop single column."""
    return df.drop(columns=[column_name])


def drop_columns(df, column_names):
    """Drop multiple columns."""
    return df.drop(columns=column_names)


def rename_column(df, old_name, new_name):
    """Rename single column."""
    return df.rename(columns={old_name: new_name})


def rename_columns(df, name_mapping):
    """Rename multiple columns."""
    return df.rename(columns=name_mapping)


# ═══════════════════════════════════════════════════════════
#  Row Selection & Filtering
# ═══════════════════════════════════════════════════════════


def select_rows(df, start, end):
    """Select rows by index."""
    return df.iloc[start:end]


def filter_where(df, column, operator, value):
    """Filter with operator."""
    ops = {
        '>': df[column] > value,
        '>=': df[column] >= value,
        '<': df[column] < value,
        '<=': df[column] <= value,
        '==': df[column] == value,
        '!=': df[column] != value,
    }
    return df[ops.get(operator, df[column] == value)]


def filter_equals(df, column, value):
    """Filter equals."""
    return df[df[column] == value]


def filter_in(df, column, values):
    """Filter in list."""
    return df[df[column].isin(values)]


def filter_not_null(df, column):
    """Filter not null."""
    return df[df[column].notna()]


def filter_contains(df, column, substring):
    """Filter string contains."""
    return df[df[column].str.contains(substring, na=False)]


def sample(df, n):
    """Random sample."""
    return df.sample(n=min(n, len(df)))


# ═══════════════════════════════════════════════════════════
#  Adding & Modifying Data
# ═══════════════════════════════════════════════════════════


def add_column(df, column_name, values):
    """Add new column."""
    result = df.copy()
    result[column_name] = values
    return result


def add_calculated_column(df, column_name, expression):
    """Add calculated column using eval."""
    result = df.copy()
    result[column_name] = result.eval(expression)
    return result


def set_value(df, row, column, value):
    """Set cell value."""
    result = df.copy()
    result.at[row, column] = value
    return result


def fill_null(df, value):
    """Fill all nulls."""
    return df.fillna(value)


def fill_null_column(df, column, value):
    """Fill nulls in column."""
    result = df.copy()
    result[column] = result[column].fillna(value)
    return result


def drop_null_rows(df):
    """Drop rows with nulls."""
    return df.dropna()


def drop_duplicates(df):
    """Drop duplicate rows."""
    return df.drop_duplicates()


# ═══════════════════════════════════════════════════════════
#  Sorting
# ═══════════════════════════════════════════════════════════


def sort_by(df, column, ascending=True):
    """Sort by column."""
    return df.sort_values(by=column, ascending=ascending)


def sort_by_columns(df, columns, ascending):
    """Sort by multiple columns."""
    return df.sort_values(by=columns, ascending=ascending)


# ═══════════════════════════════════════════════════════════
#  Grouping & Aggregation
# ═══════════════════════════════════════════════════════════


def group_by(df, columns):
    """Group by columns."""
    return df.groupby(columns)


def group_and_sum(df, group_column, sum_column):
    """Group and sum."""
    return df.groupby(group_column)[sum_column].sum().reset_index()


def group_and_mean(df, group_column, mean_column):
    """Group and mean."""
    return df.groupby(group_column)[mean_column].mean().reset_index()


def group_and_count(df, group_column):
    """Group and count."""
    return df.groupby(group_column).size().reset_index(name='count')


def aggregate(df, group_columns, agg_dict):
    """Multiple aggregations."""
    return df.groupby(group_columns).agg(agg_dict).reset_index()


def value_counts(df, column):
    """Value counts."""
    return df[column].value_counts().to_dict()


# ═══════════════════════════════════════════════════════════
#  Column Statistics
# ═══════════════════════════════════════════════════════════


def col_sum(df, column):
    """Column sum."""
    return df[column].sum()


def col_mean(df, column):
    """Column mean."""
    return df[column].mean()


def col_median(df, column):
    """Column median."""
    return df[column].median()


def col_min(df, column):
    """Column min."""
    return df[column].min()


def col_max(df, column):
    """Column max."""
    return df[column].max()


def col_std(df, column):
    """Column std."""
    return df[column].std()


# ═══════════════════════════════════════════════════════════
#  Merging & Joining
# ═══════════════════════════════════════════════════════════


def merge(df1, df2, on_column, how='inner'):
    """Merge DataFrames."""
    return pd.merge(df1, df2, on=on_column, how=how)


def join(df1, df2, how='left'):
    """Join DataFrames."""
    return df1.join(df2, how=how)


def concat(dataframes, axis=0):
    """Concatenate DataFrames."""
    return pd.concat(dataframes, axis=axis, ignore_index=True)


# ═══════════════════════════════════════════════════════════
#  Pivot & Reshape
# ═══════════════════════════════════════════════════════════


def pivot_table(df, index, columns, values, aggfunc='mean'):
    """Create pivot table."""
    return pd.pivot_table(df, index=index, columns=columns, values=values, aggfunc=aggfunc)


def melt(df, id_vars, value_vars):
    """Melt DataFrame."""
    return pd.melt(df, id_vars=id_vars, value_vars=value_vars)


def transpose(df):
    """Transpose DataFrame."""
    return df.T


# ═══════════════════════════════════════════════════════════
#  Export & Save
# ═══════════════════════════════════════════════════════════


def to_csv(df, filepath):
    """Save to CSV."""
    df.to_csv(filepath, index=False)
    return f'Saved to {filepath}'


def to_json(df, filepath):
    """Save to JSON."""
    df.to_json(filepath, orient='records', indent=2)
    return f'Saved to {filepath}'


def to_excel(df, filepath):
    """Save to Excel."""
    df.to_excel(filepath, index=False)
    return f'Saved to {filepath}'


def to_dict(df):
    """Convert to dict."""
    return df.to_dict(orient='list')


def to_records(df):
    """Convert to records."""
    return df.to_dict(orient='records')


def display(df):
    """Display DataFrame."""
    return df.to_string()
