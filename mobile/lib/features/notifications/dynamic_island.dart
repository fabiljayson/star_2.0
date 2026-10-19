import 'dart:async';

import 'package:flutter/material.dart';

import '../../theme.dart';

/// One in-app "dynamic island" style notification.
///
/// Shapes: a small pill morphs into a wide card (title tinted with [accent],
/// message below), then collapses again. Queue order is respected.
@immutable
class IslandNotification {
  const IslandNotification({
    required this.title,
    required this.id,
    this.message = '',
    this.icon = Icons.notifications_outlined,
    this.accent = StarColors.primary,
    this.duration = const Duration(seconds: 4),
    this.onTap,
  });

  final String id;
  final String title;
  final String message;
  final IconData icon;
  final Color accent;
  final Duration? duration;
  final VoidCallback? onTap;
}

/// Controller owning the visible notification and the waiting queue.
class IslandController extends ChangeNotifier {
  IslandNotification? _current;
  Timer? _autoDismiss;
  bool _disposed = false;

  IslandNotification? get current => _current;
  bool get isShowing => _current != null;

  /// Show a notification (replaces the active one, queues nothing else).
  void show(IslandNotification notification) {
    if (_disposed) return;
    _autoDismiss?.cancel();
    _current = notification;
    final lifetime = notification.duration;
    if (lifetime != null) {
      _autoDismiss = Timer(lifetime, dismiss);
    }
    notifyListeners();
  }

  /// Drop the active notification and promote the next queued one (if any).
  void dismiss() {
    if (_disposed) return;
    _autoDismiss?.cancel();
    _autoDismiss = null;
    _current = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _autoDismiss?.cancel();
    super.dispose();
  }
}

/// Overlay that draws the morphing island above its child widget subtree.
///
/// Insert exactly once, around the whole app (Navigator included), so the
/// notification floats over every screen.
class IslandOverlay extends StatefulWidget {
  const IslandOverlay({super.key, required this.controller, required this.child});

  final IslandController controller;
  final Widget child;

  static const _expandedDuration = Duration(milliseconds: 320);
  @override
  State<IslandOverlay> createState() => _IslandOverlayState();
}

class _IslandOverlayState extends State<IslandOverlay> {
  bool _expanded = false;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onController);
  }

  void _onController() {
    if (widget.controller.current == null) {
      _expanded = false;
    } else {
      // Collapsed pill first, then the card morphs out on the next frame.
      Future<void>.delayed(const Duration(milliseconds: 180), () {
        if (mounted && widget.controller.current != null) {
          setState(() => _expanded = true);
        }
      });
    }
    setState(() {});
  }

  @override
  void didUpdateWidget(covariant IslandOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_onController);
      widget.controller.addListener(_onController);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onController);
    super.dispose();
  }

  void _handleTap() {
    final notification = widget.controller.current;
    widget.controller.dismiss();
    notification?.onTap?.call();
  }

  void _dragDismiss(DragEndDetails details) {
    if (details.primaryVelocity != null && details.primaryVelocity! > 240) {
      widget.controller.dismiss();
    }
  }

  @override
  Widget build(BuildContext context) {
    final notification = widget.controller.current;
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        if (notification != null)
          Align(
            alignment: Alignment.topCenter,
            child: SafeArea(
              child: GestureDetector(
                onTap: _handleTap,
                onVerticalDragEnd: _dragDismiss,
                child: AnimatedContainer(
                  duration: IslandOverlay._expandedDuration,
                  curve: Curves.easeOutCubic,
                  margin: const EdgeInsets.only(top: 8),
                  width: _expanded
                      ? MediaQuery.of(context).size.width - 32
                      : 148,
                  height: _expanded ? 80 : 38,
                  decoration: ShapeDecoration(
                    color: StarColors.canvasDeep.withValues(alpha: 0.94),
                    shape: const StadiumBorder(),
                    shadows: _expanded ? _cardShadow : null,
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: _expanded
                      ? _CardBody(notification: notification)
                      : Center(
                          child: Icon(
                            notification.icon,
                            size: 18,
                            color: notification.accent,
                          ),
                        ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  static const _cardShadow = [
    BoxShadow(
      color: Color(0x3310161d),
      blurRadius: 24,
      offset: Offset(0, 10),
    ),
  ];
}

/// Title + message layout inside the expanded card.
class _CardBody extends StatelessWidget {
  const _CardBody({required this.notification});

  final IslandNotification notification;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Icon(notification.icon, color: notification.accent, size: 24),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(
                    child: Text(
                      notification.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleSmall
                          ?.copyWith(color: notification.accent),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Icon(Icons.priority_high, size: 14, color: notification.accent),
                ],
              ),
              if (notification.message.isEmpty)
                const SizedBox.shrink()
              else
                Text(
                  notification.message,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: StarColors.textInverseMuted),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
