# Options

Open **Settings → Devices & services → CloudScale Neutron** and press
**Configure**.

| Option | Default | What it does |
|---|---|---|
| Poll interval | 5 s | How often the scale is asked for a reading. 0.2 s to 1 hour, in steps of 0.1 s |
| Smoothing | Off | Adds smoothed weight sensors next to the live ones |
| Smoothing window | 30 s | How far back the smoothing looks |
| Smooth stable readings only | On | Leaves readings out while the scale reports the weight as moving |

## Poll interval

The scale only answers when asked, so the integration polls. A slow-changing
load, such as a bin or a tank, is fine at 5 to 30 seconds. Use a shorter
interval only if you need to follow fast changes.

## Smoothing

Switching smoothing on adds **Net weight smoothed** and **Gross weight
smoothed**. The live sensors stay as they are.

| Method | Behaviour | Good for |
|---|---|---|
| Average | Mean of the window. Steadiest; lags a real change by about the window length | Slow, steady loads |
| Median | Middle reading of the window. Ignores short spikes | Loads that get bumped or leaned on |
| Exponential | Recent readings count more; settles gradually | Following changes with less lag |

The window is in seconds, not samples, so changing the poll interval does not
change the result. For exponential smoothing the window is the time constant.

Smoothed versions of **ADC counts** and **Load cell signal** are added too,
switched off by default. The module sends ADC counts as whole numbers and
millivolts with four decimals, so averaging is the only way to get finer
resolution out of them.

Switching smoothing off removes the smoothed sensors again.
