from __future__ import annotations

from datetime import datetime

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBezierPath,
    NSButton,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSMakeRect,
    NSMinYEdge,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSStatusBar,
    NSStringDrawingUsesLineFragmentOrigin,
    NSView,
    NSViewController,
    NSVariableStatusItemLength,
)
from Foundation import NSObject, NSRunLoop, NSRunLoopCommonModes, NSString, NSTimer

from .controller import CodexLimitMonitor, DisplayState


POPOVER_WIDTH = 390
POPOVER_HEIGHT = 270


class DashboardView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(DashboardView, self).initWithFrame_(frame)
        if self is not None:
            self.state = None
        return self

    def setState_(self, state):
        self.state = state
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        bounds = self.bounds()
        NSColor.colorWithCalibratedWhite_alpha_(0.98, 0.96).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bounds, 10.0, 10.0).fill()

        state = self.state
        if state is None or state.current is None:
            self._draw_text("Codex weekly limit", 18, POPOVER_HEIGHT - 36, 18, 0.90)
            self._draw_text("No rate-limit samples found yet.", 18, POPOVER_HEIGHT - 66, 13, 0.62)
            return

        current = state.current
        title = f"{state.title} burn"
        subtitle = f"{current.used_percent:.0f}% used, {current.remaining_percent:.0f}% left"
        self._draw_text(title, 18, POPOVER_HEIGHT - 36, 20, 0.92)
        self._draw_text(subtitle, 18, POPOVER_HEIGHT - 60, 12, 0.58)

        graph_rect = NSMakeRect(18, 82, POPOVER_WIDTH - 36, 128)
        self._draw_graph(graph_rect, state)

        eta = f"ETA to zero: {state.eta_text}"
        sample_time = datetime.fromtimestamp(current.observed_at).strftime("%b %-d, %-I:%M %p")
        self._draw_text(eta, 18, 48, 13, 0.75)
        self._draw_text(f"Last sample: {sample_time}", 18, 28, 11, 0.46)
        if state.error:
            self._draw_text(state.error, 18, 10, 10, 0.50)

    def _draw_graph(self, graph_rect, state: DisplayState):
        current = state.current
        if current is None:
            return

        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.92, 0.96, 1.0, 0.72).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(graph_rect, 8.0, 8.0).fill()

        reset_start = current.reset_start
        window_seconds = max(1.0, current.window_minutes * 60.0)

        ideal = NSBezierPath.bezierPath()
        ideal.moveToPoint_((graph_rect.origin.x, graph_rect.origin.y))
        ideal.lineToPoint_((graph_rect.origin.x + graph_rect.size.width, graph_rect.origin.y + graph_rect.size.height))
        ideal.setLineWidth_(1.25)
        ideal.setLineDash_count_phase_([4.0, 4.0], 2, 0.0)
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.22, 0.36, 0.52, 0.38).setStroke()
        ideal.stroke()

        points = [
            self._point_for_sample(sample, graph_rect, reset_start, window_seconds)
            for sample in state.samples
            if reset_start <= sample.observed_at <= current.resets_at
        ]
        if not points:
            points = [self._point_for_sample(current, graph_rect, reset_start, window_seconds)]

        area = NSBezierPath.bezierPath()
        first_x, first_y = points[0]
        area.moveToPoint_((first_x, graph_rect.origin.y))
        area.lineToPoint_((first_x, first_y))
        for point in points[1:]:
            area.lineToPoint_(point)
        last_x, _last_y = points[-1]
        area.lineToPoint_((last_x, graph_rect.origin.y))
        area.closePath()
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.16, 0.55, 0.96, 0.24).setFill()
        area.fill()

        line = NSBezierPath.bezierPath()
        line.moveToPoint_(points[0])
        for point in points[1:]:
            line.lineToPoint_(point)
        line.setLineWidth_(3.0)
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.04, 0.38, 0.82, 0.92).setStroke()
        line.stroke()

        border = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(graph_rect, 8.0, 8.0)
        border.setLineWidth_(1.0)
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.30, 0.48, 0.14).setStroke()
        border.stroke()

    def _point_for_sample(self, sample, graph_rect, reset_start, window_seconds):
        x_fraction = (sample.observed_at - reset_start) / window_seconds
        x_fraction = max(0.0, min(1.0, x_fraction))
        y_fraction = max(0.0, min(1.0, sample.used_percent / 100.0))
        return (
            graph_rect.origin.x + graph_rect.size.width * x_fraction,
            graph_rect.origin.y + graph_rect.size.height * y_fraction,
        )

    def _draw_text(self, text, x, y, size, alpha):
        color = NSColor.colorWithCalibratedWhite_alpha_(0.06, alpha)
        attrs = {
            NSFontAttributeName: NSFont.systemFontOfSize_(size),
            NSForegroundColorAttributeName: color,
        }
        rect = NSMakeRect(x, y, POPOVER_WIDTH - x - 18, size + 8)
        NSString.stringWithString_(text).drawWithRect_options_attributes_(
            rect,
            NSStringDrawingUsesLineFragmentOrigin,
            attrs,
        )


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
        button.setTarget_(self)
        button.setAction_("togglePopover:")

        self.dashboard_view = DashboardView.alloc().initWithFrame_(
            NSMakeRect(0, 0, POPOVER_WIDTH, POPOVER_HEIGHT)
        )
        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, POPOVER_WIDTH, POPOVER_HEIGHT))
        container.addSubview_(self.dashboard_view)

        quit_button = NSButton.buttonWithTitle_target_action_("Quit", self, "quit:")
        quit_button.setFrame_(NSMakeRect(POPOVER_WIDTH - 72, 15, 54, 24))
        container.addSubview_(quit_button)

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

    def quit_(self, sender):
        NSApplication.sharedApplication().terminate_(sender)


def run() -> None:
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
