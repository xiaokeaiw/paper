"""
Four anomaly type illustrations for thesis Ch2.
No text. Only curves + shaded anomaly regions (uniform red).
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({
    'axes.linewidth': 0.6,
    'figure.dpi': 300,
    'savefig.dpi': 300,
})

np.random.seed(42)
OUT = 'files/Img/'
W, H = 10, 2.8

# Uniform anomaly shading style
ANOM_COLOR = '#FF9999'
ANOM_ALPHA = 0.35


def smooth(y, w=5):
    return np.convolve(y, np.ones(w)/w, mode='same')


def strip_axes(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_linewidth(0.5)


def crop_to_cycles(y, t, period, margin=0):
    """Crop to full cycles: find first and last clean cycle boundaries."""
    mean_val = np.mean(y)
    crossings = []
    for i in range(1, len(y)):
        if y[i-1] <= mean_val < y[i]:
            crossings.append(i)
    if len(crossings) < 2:
        return y, t
    start = max(0, crossings[0] - margin)
    end = min(len(y), crossings[-1] + margin)
    return y[start:end], t[start:end]


# ============================================================
# (a) Point Anomaly
# ============================================================
def plot_a():
    fig, ax = plt.subplots(figsize=(W, H))
    T = 600
    t = np.arange(T)

    y = 50 + 8*np.sin(2*np.pi*t/55) + np.random.normal(0, 0.8, T)
    y = smooth(y, 7)

    # Inject spikes into the curve
    g_pts = [90, 340]
    g_spikes = [+24, -22]
    for gp, gs in zip(g_pts, g_spikes):
        for d in range(-2, 3):
            wt = 1.0 - abs(d)/3.0
            y[gp+d] += gs * max(wt, 0)

    l_pts = [210, 450]
    l_spikes = [-11, +10]
    for lp, ls in zip(l_pts, l_spikes):
        for d in range(-2, 3):
            wt = 1.0 - abs(d)/3.0
            y[lp+d] += ls * max(wt, 0)

    # Crop to full cycles
    y, t = crop_to_cycles(y, t, 55, margin=3)

    ax.plot(t, y, color='#4472C4', lw=1.1, zorder=3)

    for gp in g_pts:
        ax.axvspan(gp-5, gp+5, color=ANOM_COLOR, alpha=ANOM_ALPHA, zorder=2)
    for lp in l_pts:
        ax.axvspan(lp-5, lp+5, color=ANOM_COLOR, alpha=ANOM_ALPHA, zorder=2)

    strip_axes(ax)
    ax.set_xlim(t[0], t[-1])
    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'anomaly_type_a_point.png', bbox_inches='tight')
    plt.savefig(OUT + 'anomaly_type_a_point.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (a)')


# ============================================================
# (b) Subsequence Anomaly
# ============================================================
def plot_b():
    fig, axes = plt.subplots(3, 1, figsize=(W, H*2.6), sharex=False)
    T = 700
    t = np.arange(T)

    # --- b1: Waveform anomaly ---
    ax = axes[0]
    y1 = 50 + 9*np.sin(2*np.pi*t/42) + np.random.normal(0, 1.0, T)
    y1 = smooth(y1, 3)
    a1s, a1e = 260, 380
    y1a = y1.copy()
    seg = t[a1s:a1e] - a1s
    y1a[a1s:a1e] = 50 + 18*np.sin(2*np.pi*seg/14) + np.random.normal(0, 1.2, a1e-a1s)
    y1a, t1 = crop_to_cycles(y1a, t, 42, margin=3)

    ax.axvspan(a1s, a1e, color=ANOM_COLOR, alpha=ANOM_ALPHA, zorder=1)
    ax.plot(t1, y1a, color='#4472C4', lw=1.1, zorder=3)
    ax.set_xlim(t1[0], t1[-1])
    strip_axes(ax)

    # --- b2: Seasonal anomaly ---
    ax = axes[1]
    y2 = 50 + 10*np.sin(2*np.pi*t/50) + np.random.normal(0, 1.0, T)
    y2 = smooth(y2, 3)
    a2s, a2e = 270, 420
    y2a = y2.copy()
    seg2 = t[a2s:a2e] - a2s
    y2a[a2s:a2e] = 50 + 4*np.sin(2*np.pi*seg2/130) + np.random.normal(0, 1.5, a2e-a2s)
    y2a, t2 = crop_to_cycles(y2a, t, 50, margin=3)

    ax.axvspan(a2s, a2e, color=ANOM_COLOR, alpha=ANOM_ALPHA, zorder=1)
    ax.plot(t2, y2a, color='#4472C4', lw=1.1, zorder=3)
    ax.set_xlim(t2[0], t2[-1])
    strip_axes(ax)

    # --- b3: Trend anomaly (smooth S-curve shift, persists after) ---
    # Use longer data; crop based on ORIGINAL (pre-shift) data to keep normal segments
    ax = axes[2]
    T3 = 900
    t3_full = np.arange(T3)
    np.random.seed(123)  # separate seed for this subplot
    normal_trend = 0.008 * t3_full
    y3_base = 40 + normal_trend + 5*np.sin(2*np.pi*t3_full/50)
    noise3 = smooth(np.random.normal(0, 1.0, T3), 3)
    y3 = y3_base + noise3
    y3 = smooth(y3, 3)

    a3s, a3e = 380, 520
    y3a = y3.copy()
    seg3 = t3_full[a3s:a3e] - a3s
    n3 = a3e - a3s
    target_shift = 10
    alpha_ramp = seg3 / n3
    shift_curve = target_shift * (3*alpha_ramp**2 - 2*alpha_ramp**3)
    y3a[a3s:a3e] = y3[a3s:a3e] + shift_curve
    y3a[a3e:] = y3[a3e:] + target_shift

    # Crop based on the ORIGINAL unshifted signal to preserve normal segments
    mean_y3 = np.mean(y3)
    crossings3 = []
    for ci in range(1, len(y3)):
        if y3[ci-1] <= mean_y3 < y3[ci]:
            crossings3.append(ci)
    if len(crossings3) >= 2:
        # Find a crossing well before a3s and well after a3e
        start3 = crossings3[0]
        end3 = crossings3[-1]
        for cx in crossings3:
            if cx < a3s - 80:
                start3 = cx
        for cx in reversed(crossings3):
            if cx > a3e + 80:
                end3 = cx
                break
        y3a = y3a[start3:end3]
        t3 = t3_full[start3:end3]
    else:
        t3 = t3_full

    ax.axvspan(a3s, a3e, color=ANOM_COLOR, alpha=ANOM_ALPHA, zorder=1)
    ax.plot(t3, y3a, color='#4472C4', lw=1.1, zorder=3)
    ax.set_xlim(t3[0], t3[-1])
    strip_axes(ax)

    np.random.seed(42)  # restore main seed

    plt.tight_layout(pad=0.3, h_pad=0.5)
    plt.savefig(OUT + 'anomaly_type_b_subsequence.png', bbox_inches='tight')
    plt.savefig(OUT + 'anomaly_type_b_subsequence.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (b)')


# ============================================================
# (c) Inter-variable Correlation Anomaly (single subplot only)
# ============================================================
def plot_c():
    fig, ax = plt.subplots(figsize=(W, H))
    T = 600
    t = np.arange(T)

    np.random.seed(200)  # fixed seed for reproducible c plot
    base = (5*np.sin(2*np.pi*t/70)
            + 3*np.sin(2*np.pi*t/30 + 1.5)
            + np.cumsum(np.random.normal(0, 0.10, T)))
    base = smooth(base, 8)

    # Low noise + heavy smoothing for clear trend/periodicity
    v1 = 50 + base + np.random.normal(0, 0.6, T)
    v2 = 48 + 0.8*base + np.random.normal(0, 0.6, T)
    v1 = smooth(v1, 10)
    v2 = smooth(v2, 10)

    acs, ace = 230, 370
    v2a = v2.copy()
    v2a[acs:ace] = 48 - 0.6*base[acs:ace] + np.random.normal(0, 0.8, ace-acs)
    v2a = smooth(v2a, 8)
    np.random.seed(42)  # restore

    # Crop both together
    mean_v1 = np.mean(v1)
    crossings = []
    for i in range(1, len(v1)):
        if v1[i-1] <= mean_v1 < v1[i]:
            crossings.append(i)
    if len(crossings) >= 2:
        start = crossings[0]
        end = crossings[-1]
        v1 = v1[start:end]
        v2a = v2a[start:end]
        t = t[start:end]

    ax.axvspan(acs, ace, color=ANOM_COLOR, alpha=ANOM_ALPHA, zorder=1)
    ax.plot(t, v1, color='#4472C4', lw=1.1, zorder=3)
    ax.plot(t, v2a, color='#ED7D31', lw=1.1, zorder=3)
    ax.set_xlim(t[0], t[-1])
    strip_axes(ax)

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'anomaly_type_c_correlation.png', bbox_inches='tight')
    plt.savefig(OUT + 'anomaly_type_c_correlation.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (c)')


# ============================================================
# (d) Node-level Anomaly
# ============================================================
def plot_d():
    fig, ax = plt.subplots(figsize=(W, H))
    T = 600
    t = np.arange(T)
    n_normal = 7

    cluster_base = (3*np.sin(2*np.pi*t/65)
                    + 1.5*np.sin(2*np.pi*t/28 + 0.7)
                    + np.cumsum(np.random.normal(0, 0.08, T)))
    cluster_base = smooth(cluster_base, 5)
    cluster_base = 50 + cluster_base

    normals = []
    blues = ['#9BB8D8','#82A8CF','#A8C8E8','#7099C4','#B0D0EC','#6B92BD','#C0D8F0']
    for i in range(n_normal):
        off = np.random.uniform(-3, 3)
        sc = np.random.uniform(0.85, 1.15)
        drift = np.cumsum(np.random.normal(0, 0.06, T))
        c = off + sc*(cluster_base - 50) + 50 + drift + np.random.normal(0, 1.8, T)
        normals.append(smooth(c, 4))

    acs = 320
    anom = np.zeros(T)
    anom[:acs] = cluster_base[:acs] + np.random.normal(0, 2.0, acs)
    seg = t[acs:] - acs
    anom[acs:] = (cluster_base[acs:]
                  + 0.06*seg
                  + 4*np.sin(2*np.pi*seg/22)
                  + np.random.normal(0, 2.2, T-acs))
    anom = smooth(anom, 4)

    # Crop all together
    mean_c = np.mean(cluster_base)
    crossings = []
    for i in range(1, len(cluster_base)):
        if cluster_base[i-1] <= mean_c < cluster_base[i]:
            crossings.append(i)
    if len(crossings) >= 2:
        start = crossings[0]
        end = crossings[-1]
        t = t[start:end]
        normals = [c[start:end] for c in normals]
        anom = anom[start:end]
        cluster_base_crop = cluster_base[start:end]
    else:
        cluster_base_crop = cluster_base

    all_n = np.array(normals)
    mn = np.mean(all_n, axis=0)
    sn = np.std(all_n, axis=0)
    ax.fill_between(t, mn-2.2*sn, mn+2.2*sn, color='#DCEAF7', alpha=0.5, zorder=1)

    for i, c in enumerate(normals):
        ax.plot(t, c, color=blues[i], lw=0.7, alpha=0.65, zorder=2)

    ax.plot(t, anom, color='#C00000', lw=1.6, zorder=5)
    ax.axvspan(acs, t[-1], color=ANOM_COLOR, alpha=ANOM_ALPHA*0.6, zorder=0)

    strip_axes(ax)
    ax.set_xlim(t[0], t[-1])
    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'anomaly_type_d_node.png', bbox_inches='tight')
    plt.savefig(OUT + 'anomaly_type_d_node.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (d)')


if __name__ == '__main__':
    import os
    os.makedirs(OUT, exist_ok=True)
    plot_a()
    plot_b()
    plot_c()
    plot_d()
    print('\nDone!')
