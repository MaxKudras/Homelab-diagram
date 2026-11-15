"""Palette and fixed sizes (same values as the original build.py)."""
W = 2400                 # canvas width (height is computed)
MARGIN = 40

BG = "#0b0f15"
GRID = "#151c26"
PANEL = "#111821"
PANEL2 = "#161f2b"
CHIP = "#19222e"
BORDER = "#253042"
TEXT = "#e6edf3"
MUTED = "#8d9aab"
FAINT = "#5d6a7c"
TRUNK = "#d5dde6"
TRUNK_BORDER = "#3a475a"   # border for devices on a tagged trunk (not in a single VLAN)
LINK = "#79c0ff"
REDDIT = "#ff5722"
DISK = "#1d2734"
DISK_EDGE = "#5a6b82"
HWC = "#c08a5c"            # "physical hardware" accent
GT = "#c08a5c"             # group titles
CONFLICT = "#ff7b72"
PROTO = {"TCP": "#79c0ff", "UDP": "#39c5cf"}
SPEED_W = {"40G": 11.5, "25G": 10.5, "10G": 9.5, "5G": 5.0, "2.5G": 3.8, "1G": 2.4, "100M": 1.4}
SANS = "Fira Sans"
MONO = "Fira Code"
TAB = 34                   # folder tab height on physical-device cards

# frame: left column (networks, legend), right column (cloud, port forwards, flows)
LEFT_X, LEFT_W = 40, 500
RIGHT_X, RIGHT_W = 1790, 570
CX = 1200                  # center line of the edge chain (internet → ISP → firewall → switch)
CENTER_L, CENTER_R = 580, 1750


def speed_w(speed):
    return SPEED_W.get(str(speed), 2.4)


def trunk_w(speed):
    return speed_w(speed) + 3.4
