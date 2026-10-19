import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_session.dart';
import '../../theme.dart';
import '../../core/api_client.dart';
import 'dynamic_island.dart';
import 'notification.dart';
import 'notifications_repository.dart';
import 'notifications_page.dart';

/// Polls for unread notifications while the app is in the foreground and
/// pushes new ones onto the dynamic island overlay.
///
/// The first sweep only records a baseline (nothing banners at login on an
/// old backlog); later sweeps raise only the truly new items.
class NotificationForegroundPoller extends StatefulWidget {
  const NotificationForegroundPoller({super.key, required this.child});

  final Widget child;

  @override
  State<NotificationForegroundPoller> createState() =>
      _NotificationForegroundPollerState();
}

class _NotificationForegroundPollerState
    extends State<NotificationForegroundPoller> {
  static const _interval = Duration(seconds: 30);

  final IslandController _island = IslandController();
  Timer? _timer;
  bool _baselineDone = false;
  Set<String> _seenIds = {};
  Set<String> _allowedCategories = {};

  AppSession get _session => context.read<AppSession>();

  @override
  void initState() {
    super.initState();
    _session.addListener(_onSession);
    _start();
  }

  void _onSession() => _start();

  void _start() {
    final signedIn = _session.phase == AuthPhase.signedIn;
    if (signedIn && _timer == null) {
      _baselineDone = false;
      _allowedCategories = {};
      _timer = Timer.periodic(_interval, (_) => _poll());
      unawaited(_poll());
    } else if (!signedIn && _timer != null) {
      _timer?.cancel();
      _timer = null;
      _island.dismiss();
    }
  }

  @override
  void dispose() {
    _session.removeListener(_onSession);
    _timer?.cancel();
    _island.dispose();
    super.dispose();
  }

  Future<void> _poll() async {
    final repository = NotificationsRepository(_session);
    try {
      final results = await Future.wait([
        repository.list(unreadOnly: true, pageSize: 5),
        repository.preferences(),
      ]);
      final unread = results[0] as List<StarNotification>;
      final preferences = results[1] as List<NotificationPreference>;
      final allowed = {
        for (final pref in preferences)
          if (pref.inApp) pref.category,
      };
      if (mounted) setState(() => _allowedCategories = allowed);
      if (!_baselineDone) {
        _seenIds = {for (final item in unread) item.id};
        if (mounted) setState(() => _baselineDone = true);
        return;
      }
      for (final item in unread) {
        if (_seenIds.contains(item.id)) continue;
        _seenIds.add(item.id);
        if (_allowedCategories.isNotEmpty && !_allowedCategories.contains(item.category)) continue;
        _island.show(IslandNotification(
          id: item.id,
          title: item.title,
          message: item.body,
          icon: _iconFor(item.category),
          accent: _accentFor(item.category),
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const NotificationsPage()),
            );
          },
        ));
        return; // one at a time; the next sweep will pick the rest up
      }
    } on ApiException catch (_) {
      // Quiet: the user will see the bell count in the UI instead.
    }
  }

  IconData _iconFor(String category) {
    switch (category) {
      case 'procedure_approved':
        return Icons.check_circle_outline;
      case 'procedure_returned':
        return Icons.undo;
      case 'assessment_result':
        return Icons.grade_outlined;
      case 'placement_update':
        return Icons.school_outlined;
      case 'examiner_assigned':
        return Icons.person_add_alt_1_outlined;
      default:
        return Icons.notifications_active_outlined;
    }
  }

  Color _accentFor(String category) {
    switch (category) {
      case 'procedure_approved':
      case 'assessment_result':
        return StarColors.success;
      case 'procedure_returned':
      case 'assessment_correction':
        return StarColors.warning;
      default:
        return StarColors.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableProvider<IslandController>.value(
      value: _island,
      child: IslandOverlay(controller: _island, child: widget.child),
    );
  }
}
