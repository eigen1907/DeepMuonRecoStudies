"""Shared drawing details for the slide plots."""

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
import numpy as np


def color_scale(ax, image, label, ticks=None):
    """Draw a slide-style colorbar in the plot's single Axes."""
    x, width = 1.06, 0.045
    maximum = image.norm.vmax
    if ticks is None:
        ticks = MaxNLocator(nbins=9, steps=[1, 2, 2.5, 5, 10]).tick_values(0, maximum)
    ticks = np.asarray(ticks)
    ticks = ticks[ticks <= maximum + 1e-12]
    step = ticks[1] - ticks[0]
    decimals = max(1, int(np.ceil(-np.log10(step))))

    ax.imshow(np.linspace(0, 1, 256)[:, None], extent=(x, x + width, 0, 1),
              transform=ax.transAxes, cmap=image.cmap, vmin=0, vmax=1,
              interpolation="nearest", aspect="auto", origin="lower", clip_on=False)
    ax.add_patch(Rectangle((x, 0), width, 1, transform=ax.transAxes,
                           fill=False, clip_on=False, edgecolor="black", lw=1))
    for value in np.arange(0, maximum + step / 100, step / 5):
        y = value / maximum
        ax.plot((x + width - 0.006, x + width), (y, y), color="black", lw=0.6,
                transform=ax.transAxes, clip_on=False)
    for value in ticks:
        y = value / maximum
        ax.plot((x + width - 0.012, x + width), (y, y), color="black", lw=0.8,
                transform=ax.transAxes, clip_on=False)
        ax.text(x + width + 0.007, y, f"{value:.{decimals}f}", va="center",
                transform=ax.transAxes, fontsize=plt.rcParams["ytick.labelsize"])
    ax.text(1.20, 0.5, label, rotation=90, va="center",
            transform=ax.transAxes, fontsize=plt.rcParams["axes.labelsize"])
