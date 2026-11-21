"""MC 像素风外观（转发出口）。

真正的绘制实现已按用途拆到 app/render/ 下：
    palette  配色与一天的光线
    common   基础画笔（填充、斜面、材质、面板、按钮）
    chrome   边框装饰件（图标、菜单按钮、草皮条）
    sky      天空（云、月亮、鸟群）
    meadow   草地（花海、草皮卷、道具、整条进度条）
    overlay  覆盖层（木牌、选项、烟花、彩纸）

这里把名字全部转出来，所以老的 `theme.xxx` 调用照旧有效。
"""
from __future__ import annotations

from .render.palette import (  # noqa: F401
    PALETTES, PALETTE_NAMES, resolve_palette, c,
    quote_color, _TIME_CURVE, _curve_at, _tint,
    palette_at,
)
from .render.common import (  # noqa: F401
    _tex_cache, _noise_block, grass_block, _scaled,
    texture, clear_cache, fill, bevel,
    draw_panel, draw_sunken, draw_bar, draw_button,
    draw_slot,
)
from .render.chrome import (  # noqa: F401
    iso_block, draw_grass_strip, draw_image_outlined, draw_menu_icon,
    pixmap_icon,
)
from .render.sky import (  # noqa: F401
    _cloud_cache, _SKY_CURVE, _SKY_DAWN_H, _SKY_NIGHT_H,
    work_sky_hour, _mix, sky_at, _cloud_img,
    _CLOUD_SPEED, _draw_sky, _draw_moon, _draw_bird,
    _draw_flock, _FLOCK_SHAPES, _BIRD,
)
from .render.meadow import (  # noqa: F401
    _SPECIES, _SPECIES_ORDER, _PETAL_COLORS, _day_picks_cache,
    _day_picks, _shade, _draw_head, _draw_flower,
    _draw_tuft, _BLOSSOM_HEADS, _draw_blossom, _draw_flower_field,
    _SOD_ROLL_TURN_PER_UNIT, _roll_radius, _roll_cells, _sod_roll,
    _PROP_FRACS, _prop_fence, _prop_hay, _prop_stones,
    _draw_props, draw_meadow_bar, draw_lunch_marker,
)
from .render.overlay import (  # noqa: F401
    draw_plank, draw_firework, _CONFETTI, draw_confetti,
    draw_choice,
)
