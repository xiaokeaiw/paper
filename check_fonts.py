import matplotlib.font_manager as fm
all_fonts = set(f.name for f in fm.fontManager.ttflist)
for f in sorted(all_fonts):
    print(f)
