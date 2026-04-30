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

from .controller import CodexLimitMonitor, DisplayState


PADDING = 18
QUIT_BUTTON_WIDTH = 42

POPOVER_WIDTH = 390
TITLE_HEIGHT = 26
SUBTITLE_HEIGHT = 18
GRAPH_HEIGHT = 90
ETA_HEIGHT = 18
SAMPLE_HEIGHT = 16

TITLE_TO_SUBTITLE = 8
SUBTITLE_TO_GRAPH = 12
GRAPH_TO_ETA = 10
ETA_TO_SAMPLE = 6

TITLE_Y = PADDING
SUBTITLE_Y = TITLE_Y + TITLE_HEIGHT + TITLE_TO_SUBTITLE
GRAPH_Y = SUBTITLE_Y + SUBTITLE_HEIGHT + SUBTITLE_TO_GRAPH
ETA_Y = GRAPH_Y + GRAPH_HEIGHT + GRAPH_TO_ETA
SAMPLE_Y = ETA_Y + ETA_HEIGHT + ETA_TO_SAMPLE
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
                SUBTITLE_Y,
                13,
                SUBTITLE_HEIGHT,
                palette.secondary_text,
            )
            self._draw_quit_button(palette)
            return

        current = state.current
        title = f"Codex weekly limit: {state.title} burn"
        subtitle = f"{current.used_percent:.0f}% used, {current.remaining_percent:.0f}% left"
        self._draw_text(title, PADDING, TITLE_Y, 18, TITLE_HEIGHT, palette.primary_text)
        self._draw_text(subtitle, PADDING, SUBTITLE_Y, 12, SUBTITLE_HEIGHT, palette.secondary_text)

        graph_rect = NSMakeRect(PADDING, GRAPH_Y, POPOVER_WIDTH - 2 * PADDING, GRAPH_HEIGHT)
        self._draw_graph(graph_rect, state, palette)

        eta = f"ETA to zero: {state.eta_text}"
        sample_time = datetime.fromtimestamp(current.observed_at).strftime("%b %-d, %-I:%M %p")
        self._draw_text(eta, PADDING, ETA_Y, 13, ETA_HEIGHT, palette.secondary_text)
        footer = state.error or f"Last sample: {sample_time}"
        self._draw_footer(footer, palette)

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

    def _draw_graph(self, graph_rect, state: DisplayState, palette: Palette):
        current = state.current
        if current is None:
            return

        graph_path = NSBezierPath.bezierPathWithRect_(graph_rect)
        palette.graph_fill.setFill()
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
        palette.ideal_line.setStroke()
        ideal.stroke()

        points = [
            self._point_for_sample(sample, graph_rect, reset_start, window_seconds)
            for sample in state.samples
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
        palette.area_fill.setFill()
        area.fill()

        line = NSBezierPath.bezierPath()
        line.moveToPoint_(points[0])
        for point in points[1:]:
            line.lineToPoint_(point)
        line.setLineWidth_(hairline_width)
        line.setLineCapStyle_(NSButtLineCapStyle)
        palette.data_line.setStroke()
        line.stroke()
        NSGraphicsContext.restoreGraphicsState()

        graph_path.setLineWidth_(1.0)
        palette.graph_border.setStroke()
        graph_path.stroke()

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
        self.refresh_(None)
        self.popover.showRelativeToRect_ofView_preferredEdge_(
            sender.bounds(),
            sender,
            NSMinYEdge,
        )

    def refresh_(self, timer):
        try:
            state = self.monitor.refresh(backfill=False)
        except Exception as exc:
            state = DisplayState(
                [],
                None,
                None,
                "--",
                "unknown",
                f"Refresh failed: {exc}",
                0.0,
            )
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
