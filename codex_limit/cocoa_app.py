from __future__ import annotations

from datetime import datetime

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSAppearanceNameAqua,
    NSAppearanceNameDarkAqua,
    NSBezierPath,
    NSButtLineCapStyle,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSMakeRect,
    NSMinYEdge,
    NSEventModifierFlagOption,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSStatusBar,
    NSMutableParagraphStyle,
    NSParagraphStyleAttributeName,
    NSStringDrawingUsesLineFragmentOrigin,
    NSTextAlignmentRight,
    NSView,
    NSViewController,
    NSVariableStatusItemLength,
)
from Foundation import NSObject, NSRunLoop, NSRunLoopCommonModes, NSString, NSTimer

from .controller import CodexLimitMonitor, DisplayState, LimitDisplayState
from .metrics import BurnRate


PADDING = 18
QUIT_BUTTON_WIDTH = 42

POPOVER_WIDTH = 390
TITLE_HEIGHT = 26
SECTION_TITLE_HEIGHT = 22
STATS_HEIGHT = 18
GRAPH_HEIGHT = 78
SAMPLE_HEIGHT = 16

TITLE_TO_STATS = 6
STATS_TO_GRAPH = 8
GRAPH_TO_SECTION = 16
GRAPH_TO_SAMPLE = 12

TITLE_Y = PADDING
WEEKLY_STATS_Y = TITLE_Y + TITLE_HEIGHT + TITLE_TO_STATS
WEEKLY_GRAPH_Y = WEEKLY_STATS_Y + STATS_HEIGHT + STATS_TO_GRAPH
FIVE_HOUR_TITLE_Y = WEEKLY_GRAPH_Y + GRAPH_HEIGHT + GRAPH_TO_SECTION
FIVE_HOUR_STATS_Y = FIVE_HOUR_TITLE_Y + SECTION_TITLE_HEIGHT + TITLE_TO_STATS
FIVE_HOUR_GRAPH_Y = FIVE_HOUR_STATS_Y + STATS_HEIGHT + STATS_TO_GRAPH
SAMPLE_Y = FIVE_HOUR_GRAPH_Y + GRAPH_HEIGHT + GRAPH_TO_SAMPLE
POPOVER_HEIGHT = SAMPLE_Y + SAMPLE_HEIGHT + PADDING


class Palette:
    def __init__(self, dark: bool):
        if dark:
            self.background = NSColor.colorWithCalibratedWhite_alpha_(0.10, 0.98)
            self.primary_text = NSColor.colorWithCalibratedWhite_alpha_(0.96, 0.94)
            self.secondary_text = NSColor.colorWithCalibratedWhite_alpha_(0.78, 0.72)
            self.muted_text = NSColor.colorWithCalibratedWhite_alpha_(0.64, 0.62)
            self.quit_text = NSColor.colorWithCalibratedWhite_alpha_(0.72, 0.70)
            self.graph_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.06, 0.14, 0.22, 0.84
            )
            self.area_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.12, 0.52, 1.00, 0.30
            )
            self.data_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.28, 0.68, 1.00, 0.96
            )
            self.ideal_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.60, 0.75, 0.90, 0.42
            )
            self.graph_border = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.55, 0.72, 0.90, 0.26
            )
            self.green_graph_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.05, 0.18, 0.13, 0.82
            )
            self.green_area_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.14, 0.72, 0.42, 0.30
            )
            self.green_data_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.34, 0.90, 0.58, 0.96
            )
            self.green_ideal_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.62, 0.86, 0.72, 0.40
            )
            self.green_graph_border = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.55, 0.86, 0.65, 0.25
            )
        else:
            self.background = NSColor.colorWithCalibratedWhite_alpha_(0.98, 0.96)
            self.primary_text = NSColor.colorWithCalibratedWhite_alpha_(0.06, 0.92)
            self.secondary_text = NSColor.colorWithCalibratedWhite_alpha_(0.06, 0.58)
            self.muted_text = NSColor.colorWithCalibratedWhite_alpha_(0.06, 0.46)
            self.quit_text = NSColor.colorWithCalibratedWhite_alpha_(0.06, 0.54)
            self.graph_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.86, 0.93, 1.00, 0.76
            )
            self.area_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.16, 0.55, 0.96, 0.24
            )
            self.data_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.04, 0.38, 0.82, 0.92
            )
            self.ideal_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.22, 0.36, 0.52, 0.38
            )
            self.graph_border = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.15, 0.30, 0.48, 0.14
            )
            self.green_graph_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.87, 0.97, 0.91, 0.74
            )
            self.green_area_fill = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.08, 0.62, 0.30, 0.23
            )
            self.green_data_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.03, 0.48, 0.20, 0.92
            )
            self.green_ideal_line = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.20, 0.46, 0.28, 0.36
            )
            self.green_graph_border = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.12, 0.36, 0.20, 0.14
            )


class DashboardView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(DashboardView, self).initWithFrame_(frame)
        if self is not None:
            self.state = None
        return self

    def setState_(self, state):
        self.state = state
        self.setNeedsDisplay_(True)

    def isFlipped(self):
        return True

    def acceptsFirstMouse_(self, event):
        return True

    def drawRect_(self, rect):
        palette = self._palette()
        bounds = self.bounds()
        palette.background.setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bounds, 10.0, 10.0).fill()

        state = self.state
        if state is None or state.current is None:
            self._draw_text(
                "Codex weekly limit",
                PADDING,
                TITLE_Y,
                18,
                TITLE_HEIGHT,
                palette.primary_text,
            )
            self._draw_text(
                "No rate-limit samples found yet.",
                PADDING,
                WEEKLY_STATS_Y,
                13,
                STATS_HEIGHT,
                palette.secondary_text,
            )
            self._draw_quit_button(palette)
            return

        weekly = state.weekly
        self._draw_text(
            f"Codex weekly limit: {weekly.title} burn",
            PADDING,
            TITLE_Y,
            18,
            TITLE_HEIGHT,
            palette.primary_text,
        )
        self._draw_limit_stats(weekly, WEEKLY_STATS_Y, palette)

        weekly_graph_rect = NSMakeRect(
            PADDING,
            WEEKLY_GRAPH_Y,
            POPOVER_WIDTH - 2 * PADDING,
            GRAPH_HEIGHT,
        )
        self._draw_graph(weekly_graph_rect, weekly, palette, accent="blue")

        five_hour = state.five_hour
        if five_hour is not None and five_hour.current is not None:
            five_title = f"5-hour limit: {five_hour.title} burn"
            self._draw_text(
                five_title,
                PADDING,
                FIVE_HOUR_TITLE_Y,
                15,
                SECTION_TITLE_HEIGHT,
                palette.primary_text,
            )
            self._draw_limit_stats(five_hour, FIVE_HOUR_STATS_Y, palette)
            five_graph_rect = NSMakeRect(
                PADDING,
                FIVE_HOUR_GRAPH_Y,
                POPOVER_WIDTH - 2 * PADDING,
                GRAPH_HEIGHT,
            )
            self._draw_graph(five_graph_rect, five_hour, palette, accent="green")
        else:
            self._draw_text(
                "5-hour limit",
                PADDING,
                FIVE_HOUR_TITLE_Y,
                15,
                SECTION_TITLE_HEIGHT,
                palette.primary_text,
            )
            self._draw_text(
                "No 5-hour samples found yet.",
                PADDING,
                FIVE_HOUR_STATS_Y,
                12,
                STATS_HEIGHT,
                palette.secondary_text,
            )

        footer = state.error or f"Last sample: {self._last_sample_text(state)}"
        self._draw_footer(footer, palette)

    def _draw_limit_stats(
        self,
        limit: LimitDisplayState,
        y,
        palette: Palette,
    ):
        current = limit.current
        if current is None:
            return
        text = (
            f"{current.used_percent:.0f}% used, "
            f"{current.remaining_percent:.0f}% left ({limit.eta_text})"
        )
        self._draw_text(text, PADDING, y, 12, STATS_HEIGHT, palette.secondary_text)

    def _last_sample_text(self, state: DisplayState):
        candidates = [
            limit.current
            for limit in (state.weekly, state.five_hour)
            if limit is not None and limit.current is not None
        ]
        latest = max(candidates, key=lambda sample: sample.observed_at)
        return datetime.fromtimestamp(latest.observed_at).strftime("%b %-d, %-I:%M %p")

    def _draw_footer(self, text, palette: Palette):
        quit_rect = self._draw_quit_button(palette)
        self._draw_text(
            text,
            PADDING,
            SAMPLE_Y,
            11,
            SAMPLE_HEIGHT,
            palette.muted_text,
            quit_rect.origin.x - PADDING - 12,
        )

    def _draw_quit_button(self, palette: Palette):
        quit_rect = self._quit_button_rect()
        self._draw_text(
            "Quit",
            quit_rect.origin.x,
            quit_rect.origin.y,
            11,
            quit_rect.size.height,
            palette.quit_text,
            quit_rect.size.width,
            right_aligned=True,
        )
        return quit_rect

    def _draw_graph(
        self,
        graph_rect,
        limit: LimitDisplayState,
        palette: Palette,
        *,
        accent: str,
    ):
        current = limit.current
        if current is None:
            return
        colors = self._graph_colors(palette, accent)

        graph_path = NSBezierPath.bezierPathWithRect_(graph_rect)
        colors["fill"].setFill()
        graph_path.fill()

        reset_start = current.reset_start
        window_seconds = max(1.0, current.window_minutes * 60.0)
        plot_bottom = graph_rect.origin.y + graph_rect.size.height

        NSGraphicsContext.saveGraphicsState()
        graph_path.addClip()
        ideal = NSBezierPath.bezierPath()
        ideal.moveToPoint_((graph_rect.origin.x, plot_bottom))
        ideal.lineToPoint_(
            (
                graph_rect.origin.x + graph_rect.size.width,
                graph_rect.origin.y,
            )
        )
        ideal.setLineWidth_(1.25)
        ideal.setLineDash_count_phase_([4.0, 4.0], 2, 0.0)
        colors["ideal"].setStroke()
        ideal.stroke()

        points = [
            self._point_for_sample(sample, graph_rect, reset_start, window_seconds)
            for sample in limit.samples
            if reset_start <= sample.observed_at <= current.resets_at
        ]
        if not points:
            points = [self._point_for_sample(current, graph_rect, reset_start, window_seconds)]

        hairline_width = self._hairline_width()
        area = NSBezierPath.bezierPath()
        first_x, first_y = points[0]
        area.moveToPoint_((first_x, plot_bottom))
        area.lineToPoint_((first_x, first_y))
        for point in points[1:]:
            area.lineToPoint_(point)
        last_x, last_y = points[-1]
        visible_last_x = min(graph_rect.origin.x + graph_rect.size.width, last_x + hairline_width)
        area.lineToPoint_((visible_last_x, last_y))
        area.lineToPoint_((visible_last_x, plot_bottom))
        area.closePath()
        colors["area"].setFill()
        area.fill()

        line = NSBezierPath.bezierPath()
        line.moveToPoint_(points[0])
        for point in points[1:]:
            line.lineToPoint_(point)
        line.setLineWidth_(hairline_width)
        line.setLineCapStyle_(NSButtLineCapStyle)
        colors["line"].setStroke()
        line.stroke()
        NSGraphicsContext.restoreGraphicsState()

        graph_path.setLineWidth_(1.0)
        colors["border"].setStroke()
        graph_path.stroke()

    def _graph_colors(self, palette: Palette, accent: str):
        if accent == "green":
            return {
                "fill": palette.green_graph_fill,
                "area": palette.green_area_fill,
                "line": palette.green_data_line,
                "ideal": palette.green_ideal_line,
                "border": palette.green_graph_border,
            }
        return {
            "fill": palette.graph_fill,
            "area": palette.area_fill,
            "line": palette.data_line,
            "ideal": palette.ideal_line,
            "border": palette.graph_border,
        }

    def _point_for_sample(self, sample, graph_rect, reset_start, window_seconds):
        x_fraction = (sample.observed_at - reset_start) / window_seconds
        x_fraction = max(0.0, min(1.0, x_fraction))
        y_fraction = max(0.0, min(1.0, sample.used_percent / 100.0))
        return (
            graph_rect.origin.x + graph_rect.size.width * x_fraction,
            graph_rect.origin.y + graph_rect.size.height * (1.0 - y_fraction),
        )

    def _draw_text(self, text, x, y, size, height, color, width=None, right_aligned=False):
        attrs = {
            NSFontAttributeName: NSFont.systemFontOfSize_(size),
            NSForegroundColorAttributeName: color,
        }
        if right_aligned:
            paragraph = NSMutableParagraphStyle.alloc().init()
            paragraph.setAlignment_(NSTextAlignmentRight)
            attrs[NSParagraphStyleAttributeName] = paragraph
        rect = NSMakeRect(x, y, width if width is not None else POPOVER_WIDTH - x - PADDING, height)
        NSString.stringWithString_(text).drawWithRect_options_attributes_(
            rect,
            NSStringDrawingUsesLineFragmentOrigin,
            attrs,
        )

    def _quit_button_rect(self):
        return NSMakeRect(
            POPOVER_WIDTH - PADDING - QUIT_BUTTON_WIDTH,
            SAMPLE_Y,
            QUIT_BUTTON_WIDTH,
            SAMPLE_HEIGHT,
        )

    def _hairline_width(self):
        window = self.window()
        if window is None:
            return 1.0
        return 1.0 / max(1.0, window.backingScaleFactor())

    def mouseDown_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        quit_rect = self._quit_button_rect()
        if (
            quit_rect.origin.x <= point.x <= quit_rect.origin.x + quit_rect.size.width
            and quit_rect.origin.y <= point.y <= quit_rect.origin.y + quit_rect.size.height
        ):
            NSApplication.sharedApplication().terminate_(self)
            return
        objc.super(DashboardView, self).mouseDown_(event)

    def _palette(self):
        match = self.effectiveAppearance().bestMatchFromAppearancesWithNames_(
            [NSAppearanceNameAqua, NSAppearanceNameDarkAqua]
        )
        return Palette(match == NSAppearanceNameDarkAqua)

    def viewDidChangeEffectiveAppearance(self):
        self.setNeedsDisplay_(True)


class AppDelegate(NSObject):
    def init(self):
        self = objc.super(AppDelegate, self).init()
        if self is not None:
            self.monitor = CodexLimitMonitor()
            self.status_item = None
            self.popover = None
            self.dashboard_view = None
            self.timer = None
            self.latest_state = None
            self.refreshing = False
        return self

    def applicationDidFinishLaunching_(self, notification):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        button = self.status_item.button()
        button.setTitle_("--")
        button.setToolTip_("Click for details.")
        button.setTarget_(self)
        button.setAction_("togglePopover:")

        self.dashboard_view = DashboardView.alloc().initWithFrame_(
            NSMakeRect(0, 0, POPOVER_WIDTH, POPOVER_HEIGHT)
        )
        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, POPOVER_WIDTH, POPOVER_HEIGHT))
        container.addSubview_(self.dashboard_view)

        controller = NSViewController.alloc().init()
        controller.setView_(container)

        self.popover = NSPopover.alloc().init()
        self.popover.setBehavior_(NSPopoverBehaviorTransient)
        self.popover.setContentViewController_(controller)

        self.refresh_(None)
        self.timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            60.0,
            self,
            "refresh:",
            None,
            True,
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, NSRunLoopCommonModes)

    def togglePopover_(self, sender):
        event = NSApplication.sharedApplication().currentEvent()
        if event is not None and event.modifierFlags() & NSEventModifierFlagOption:
            NSApplication.sharedApplication().terminate_(sender)
            return
        if self.popover.isShown():
            self.popover.performClose_(sender)
            return
        if self.latest_state is not None:
            self.dashboard_view.setState_(self.latest_state)
        self.popover.showRelativeToRect_ofView_preferredEdge_(
            sender.bounds(),
            sender,
            NSMinYEdge,
        )

    def refresh_(self, timer):
        if self.refreshing:
            return
        self.refreshing = True
        try:
            state = self.monitor.refresh(backfill=False)
        except Exception as exc:
            weekly = LimitDisplayState(
                [],
                None,
                BurnRate(0.0, 0.0, None, None),
                "--",
                "unknown",
                f"Refresh failed: {exc}",
            )
            state = DisplayState(
                weekly,
                None,
                0.0,
            )
        finally:
            self.refreshing = False
        self.latest_state = state
        if self.status_item is not None:
            self.status_item.button().setTitle_(state.title)
        if self.dashboard_view is not None:
            self.dashboard_view.setState_(state)


def run() -> None:
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
