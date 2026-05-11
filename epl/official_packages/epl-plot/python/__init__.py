"""
EPL Plot Package - Python Backend
Matplotlib-powered plotting for EPL.
"""

import matplotlib

matplotlib.use('Agg')  # Non-interactive backend for headless operation
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np

_current_fig = None
_current_axes = None

# ═══════════════════════════════════════════════════════════
#  Figure Management
# ═══════════════════════════════════════════════════════════


def create_figure(width=10, height=6):
    """Create new figure."""
    global _current_fig, _current_axes
    _current_fig, _current_axes = plt.subplots(figsize=(width, height))
    return {'fig': id(_current_fig), 'axes': id(_current_axes)}


def create_subplots(rows=1, cols=1):
    """Create figure with subplots."""
    global _current_fig, _current_axes
    _current_fig, _current_axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 4))
    return {'fig': id(_current_fig), 'shape': (rows, cols)}


def select_subplot(fig_info, row, col):
    """Select subplot."""
    global _current_axes
    if hasattr(_current_axes, '__getitem__'):
        _current_axes = _current_axes[row, col] if _current_axes.ndim > 1 else _current_axes[row]
    return True


def show():
    """Show plot (saves to temp file in headless mode)."""
    plt.tight_layout()
    plt.show()
    return 'Plot displayed'


def savefig(filepath, dpi=150):
    """Save plot to file."""
    plt.tight_layout()
    plt.savefig(filepath, dpi=dpi, bbox_inches='tight')
    return f'Saved to {filepath}'


def close():
    """Close current plot."""
    plt.close()
    return 'Plot closed'


def clear():
    """Clear current plot."""
    plt.clf()
    return 'Plot cleared'


# ═══════════════════════════════════════════════════════════
#  Line Plots
# ═══════════════════════════════════════════════════════════


def plot(x, y, label=None, color=None, style='-'):
    """Line plot."""
    kwargs = {'label': label, 'linestyle': style}
    if color:
        kwargs['color'] = color
    plt.plot(np.asarray(x), np.asarray(y), **kwargs)
    return 'Line plotted'


def plot_multiple(datasets):
    """Plot multiple lines."""
    for ds in datasets:
        kwargs = {'label': ds.get('label')}
        if ds.get('color'):
            kwargs['color'] = ds['color']
        if ds.get('style'):
            kwargs['linestyle'] = ds['style']
        plt.plot(np.asarray(ds['x']), np.asarray(ds['y']), **kwargs)
    return f'Plotted {len(datasets)} lines'


def plot_function(func, x_min, x_max, num_points=100, label=None):
    """Plot a function."""
    x = np.linspace(x_min, x_max, num_points)
    y = np.array([func(xi) for xi in x])
    plt.plot(x, y, label=label)
    return 'Function plotted'


# ═══════════════════════════════════════════════════════════
#  Scatter Plots
# ═══════════════════════════════════════════════════════════


def scatter(x, y, label=None, color=None, size=50):
    """Scatter plot."""
    kwargs = {'label': label, 's': size}
    if color:
        kwargs['c'] = color
    plt.scatter(np.asarray(x), np.asarray(y), **kwargs)
    return 'Scatter plotted'


def scatter_colors(x, y, colors, colormap='viridis'):
    """Scatter with color-coded points."""
    plt.scatter(np.asarray(x), np.asarray(y), c=np.asarray(colors), cmap=colormap)
    return 'Scatter with colors plotted'


def scatter_sizes(x, y, sizes):
    """Scatter with variable sizes."""
    plt.scatter(np.asarray(x), np.asarray(y), s=np.asarray(sizes))
    return 'Scatter with sizes plotted'


# ═══════════════════════════════════════════════════════════
#  Bar Charts
# ═══════════════════════════════════════════════════════════


def bar(categories, values, label=None, color=None):
    """Vertical bar chart."""
    kwargs = {'label': label}
    if color:
        kwargs['color'] = color
    plt.bar(categories, np.asarray(values), **kwargs)
    return 'Bar chart created'


def barh(categories, values, label=None, color=None):
    """Horizontal bar chart."""
    kwargs = {'label': label}
    if color:
        kwargs['color'] = color
    plt.barh(categories, np.asarray(values), **kwargs)
    return 'Horizontal bar chart created'


def bar_grouped(categories, datasets, labels, colors=None):
    """Grouped bar chart."""
    x = np.arange(len(categories))
    width = 0.8 / len(datasets)
    for i, (data, label) in enumerate(zip(datasets, labels)):
        offset = width * i - width * (len(datasets) - 1) / 2
        color = colors[i] if colors and i < len(colors) else None
        plt.bar(x + offset, np.asarray(data), width, label=label, color=color)
    plt.xticks(x, categories)
    return 'Grouped bar chart created'


def bar_stacked(categories, datasets, labels, colors=None):
    """Stacked bar chart."""
    bottom = np.zeros(len(categories))
    for i, (data, label) in enumerate(zip(datasets, labels)):
        color = colors[i] if colors and i < len(colors) else None
        plt.bar(categories, np.asarray(data), bottom=bottom, label=label, color=color)
        bottom += np.asarray(data)
    return 'Stacked bar chart created'


# ═══════════════════════════════════════════════════════════
#  Histograms
# ═══════════════════════════════════════════════════════════


def hist(data, bins=10, label=None, color=None, alpha=0.7):
    """Histogram."""
    kwargs = {'bins': bins, 'label': label, 'alpha': alpha}
    if color:
        kwargs['color'] = color
    plt.hist(np.asarray(data), **kwargs)
    return 'Histogram created'


def hist2d(x, y, bins=30):
    """2D histogram."""
    plt.hist2d(np.asarray(x), np.asarray(y), bins=bins)
    return '2D histogram created'


# ═══════════════════════════════════════════════════════════
#  Pie Charts
# ═══════════════════════════════════════════════════════════


def pie(values, labels=None, colors=None, explode=None):
    """Pie chart."""
    kwargs = {'labels': labels, 'autopct': '%1.1f%%'}
    if colors:
        kwargs['colors'] = colors
    if explode:
        kwargs['explode'] = explode
    plt.pie(np.asarray(values), **kwargs)
    plt.axis('equal')
    return 'Pie chart created'


def donut(values, labels=None, colors=None):
    """Donut chart."""
    kwargs = {'labels': labels, 'autopct': '%1.1f%%', 'pctdistance': 0.85}
    if colors:
        kwargs['colors'] = colors
    wedges, texts, autotexts = plt.pie(np.asarray(values), **kwargs)
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    plt.gca().add_patch(centre_circle)
    plt.axis('equal')
    return 'Donut chart created'


# ═══════════════════════════════════════════════════════════
#  Area & Fill Plots
# ═══════════════════════════════════════════════════════════


def fill(x, y, label=None, color=None, alpha=0.5):
    """Filled area plot."""
    kwargs = {'label': label, 'alpha': alpha}
    if color:
        kwargs['color'] = color
    plt.fill(np.asarray(x), np.asarray(y), **kwargs)
    return 'Area plot created'


def fill_between(x, y1, y2, label=None, color=None, alpha=0.3):
    """Fill between two lines."""
    kwargs = {'label': label, 'alpha': alpha}
    if color:
        kwargs['color'] = color
    plt.fill_between(np.asarray(x), np.asarray(y1), np.asarray(y2), **kwargs)
    return 'Fill between created'


def stackplot(x, datasets, labels=None, colors=None):
    """Stacked area chart."""
    data = [np.asarray(d) for d in datasets]
    kwargs = {}
    if labels:
        kwargs['labels'] = labels
    if colors:
        kwargs['colors'] = colors
    plt.stackplot(np.asarray(x), *data, **kwargs)
    return 'Stacked area chart created'


# ═══════════════════════════════════════════════════════════
#  Box & Violin Plots
# ═══════════════════════════════════════════════════════════


def boxplot(data, labels=None):
    """Box plot."""
    plt.boxplot([np.asarray(d) for d in data], labels=labels)
    return 'Box plot created'


def violinplot(data, labels=None):
    """Violin plot."""
    parts = plt.violinplot([np.asarray(d) for d in data])
    if labels:
        plt.xticks(range(1, len(labels) + 1), labels)
    return 'Violin plot created'


# ═══════════════════════════════════════════════════════════
#  Heatmaps & Contours
# ═══════════════════════════════════════════════════════════


def heatmap(data, x_labels=None, y_labels=None, colormap='viridis', show_values=False):
    """Heatmap."""
    data = np.asarray(data)
    im = plt.imshow(data, cmap=colormap, aspect='auto')
    if x_labels:
        plt.xticks(range(len(x_labels)), x_labels)
    if y_labels:
        plt.yticks(range(len(y_labels)), y_labels)
    if show_values:
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                plt.text(j, i, f'{data[i, j]:.2f}', ha='center', va='center')
    plt.colorbar(im)
    return 'Heatmap created'


def contour(x, y, z, levels=10, colormap='viridis'):
    """Contour plot."""
    cs = plt.contour(np.asarray(x), np.asarray(y), np.asarray(z), levels=levels, cmap=colormap)
    plt.clabel(cs, inline=True, fontsize=8)
    return 'Contour plot created'


def contourf(x, y, z, levels=10, colormap='viridis'):
    """Filled contour plot."""
    plt.contourf(np.asarray(x), np.asarray(y), np.asarray(z), levels=levels, cmap=colormap)
    plt.colorbar()
    return 'Filled contour created'


# ═══════════════════════════════════════════════════════════
#  Error Bars
# ═══════════════════════════════════════════════════════════


def errorbar(x, y, yerr, label=None, color=None):
    """Line plot with error bars."""
    kwargs = {'label': label, 'capsize': 3}
    if color:
        kwargs['color'] = color
    plt.errorbar(np.asarray(x), np.asarray(y), yerr=np.asarray(yerr), **kwargs)
    return 'Error bar plot created'


def bar_error(categories, values, errors, label=None, color=None):
    """Bar chart with error bars."""
    kwargs = {'label': label, 'capsize': 3}
    if color:
        kwargs['color'] = color
    plt.bar(categories, np.asarray(values), yerr=np.asarray(errors), **kwargs)
    return 'Bar chart with errors created'


# ═══════════════════════════════════════════════════════════
#  Customization - Titles & Labels
# ═══════════════════════════════════════════════════════════


def title(text, fontsize=14):
    """Set title."""
    plt.title(text, fontsize=fontsize)
    return 'Title set'


def xlabel(text, fontsize=12):
    """Set x label."""
    plt.xlabel(text, fontsize=fontsize)
    return 'X label set'


def ylabel(text, fontsize=12):
    """Set y label."""
    plt.ylabel(text, fontsize=fontsize)
    return 'Y label set'


def legend(loc='best'):
    """Add legend."""
    plt.legend(loc=loc)
    return 'Legend added'


# ═══════════════════════════════════════════════════════════
#  Customization - Axes
# ═══════════════════════════════════════════════════════════


def xlim(min_val, max_val):
    """Set x limits."""
    plt.xlim(min_val, max_val)
    return 'X limits set'


def ylim(min_val, max_val):
    """Set y limits."""
    plt.ylim(min_val, max_val)
    return 'Y limits set'


def xticks(positions, labels=None):
    """Set x ticks."""
    if labels:
        plt.xticks(positions, labels)
    else:
        plt.xticks(positions)
    return 'X ticks set'


def yticks(positions, labels=None):
    """Set y ticks."""
    if labels:
        plt.yticks(positions, labels)
    else:
        plt.yticks(positions)
    return 'Y ticks set'


def set_log(axis='y'):
    """Set log scale."""
    if axis == 'x':
        plt.xscale('log')
    elif axis == 'y':
        plt.yscale('log')
    else:
        plt.xscale('log')
        plt.yscale('log')
    return f'Log scale set for {axis}'


def invert_axis(axis):
    """Invert axis."""
    if axis == 'x':
        plt.gca().invert_xaxis()
    else:
        plt.gca().invert_yaxis()
    return f'{axis} axis inverted'


# ═══════════════════════════════════════════════════════════
#  Customization - Grid & Style
# ═══════════════════════════════════════════════════════════


def grid(show=True, which='major', axis='both'):
    """Add grid."""
    plt.grid(show, which=which, axis=axis)
    return 'Grid configured'


def style(name):
    """Set plot style."""
    plt.style.use(name)
    return f'Style set to {name}'


def set_cmap(colormap):
    """Set colormap."""
    plt.set_cmap(colormap)
    return f'Colormap set to {colormap}'


# ═══════════════════════════════════════════════════════════
#  Annotations & Shapes
# ═══════════════════════════════════════════════════════════


def text(x, y, txt, fontsize=12, color='black'):
    """Add text."""
    plt.text(x, y, txt, fontsize=fontsize, color=color)
    return 'Text added'


def annotate(txt, xy, xytext=None, arrow=True):
    """Add annotation."""
    kwargs = {'xy': xy}
    if xytext:
        kwargs['xytext'] = xytext
        if arrow:
            kwargs['arrowprops'] = {'arrowstyle': '->'}
    plt.annotate(txt, **kwargs)
    return 'Annotation added'


def axhline(y, label=None, color='gray', linestyle='--'):
    """Horizontal line."""
    plt.axhline(y=y, color=color, linestyle=linestyle, label=label)
    return 'Horizontal line added'


def axvline(x, label=None, color='gray', linestyle='--'):
    """Vertical line."""
    plt.axvline(x=x, color=color, linestyle=linestyle, label=label)
    return 'Vertical line added'


def axhspan(ymin, ymax, color='yellow', alpha=0.3):
    """Horizontal span."""
    plt.axhspan(ymin, ymax, color=color, alpha=alpha)
    return 'Horizontal span added'


def axvspan(xmin, xmax, color='gray', alpha=0.2):
    """Vertical span."""
    plt.axvspan(xmin, xmax, color=color, alpha=alpha)
    return 'Vertical span added'


# ═══════════════════════════════════════════════════════════
#  Color Utilities
# ═══════════════════════════════════════════════════════════


def get_palette(name='tab10', n=10):
    """Get color palette."""
    cmap = cm.get_cmap(name, n)
    return [matplotlib.colors.rgb2hex(cmap(i)) for i in range(n)]


def colorbar(label=None):
    """Add colorbar."""
    cb = plt.colorbar()
    if label:
        cb.set_label(label)
    return 'Colorbar added'
