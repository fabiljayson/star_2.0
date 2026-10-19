import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'notification.dart';
import 'notifications_repository.dart';

/// In-app notification center.
class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  late final NotificationsRepository _repo;
  List<StarNotification>? _items;
  bool _unreadOnly = false;
  String? _error;
  bool _working = false;

  @override
  void initState() {
    super.initState();
    _repo = NotificationsRepository(context.read<AppSession>());
    _reload();
  }

  Future<void> _reload() async {
    setState(() => _error = null);
    try {
      final items = await _repo.list(unreadOnly: _unreadOnly);
      if (mounted) setState(() => _items = items);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  Future<void> _markRead(StarNotification item) async {
    if (item.isRead) return;
    setState(() => _working = true);
    try {
      await _repo.markRead(item.id);
      await _reload();
    } on ApiException catch (error) {
      if (mounted) _showErrorBar(error.friendlyMessage);
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _markAllRead() async {
    setState(() => _working = true);
    try {
      await _repo.markAllRead();
      await _reload();
    } on ApiException catch (error) {
      if (mounted) _showErrorBar(error.friendlyMessage);
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _openPreferences() async {
    FocusScope.of(context).unfocus();
    final session = context.read<AppSession>();
    final prefsRepo = NotificationsRepository(session);
    try {
      final prefs = await prefsRepo.preferences();
      if (mounted) {
        await showModalBottomSheet<void>(
          context: context,
          builder: (_) => _PreferencesSheet(
            initial: prefs,
            repository: prefsRepo,
          ),
          isScrollControlled: true,
        );
        await _reload();
      }
    } on ApiException catch (error) {
      if (mounted) _showErrorBar(error.friendlyMessage);
    }
  }

  void _showErrorBar(String message) =>
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
      );

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(
            tooltip: 'Notification preferences',
            icon: const Icon(Icons.tune),
            onPressed: _working ? null : _openPreferences,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _reload,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            Row(
              children: [
                const Text('Unread only'),
                const SizedBox(width: 4),
                Switch(
                  value: _unreadOnly,
                  onChanged: _working
                      ? null
                      : (value) {
                          setState(() => _unreadOnly = value);
                          _reload();
                        },
                ),
                const Spacer(),
                TextButton(
                  onPressed: _items == null || _working ? null : _markAllRead,
                  child: const Text('Mark all read'),
                ),
              ],
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              ErrorNotice(message: _error!),
            ],
            if (_error == null && items == null) ...[
              const SizedBox(height: 40),
              const Center(child: CircularProgressIndicator()),
            ],
            if (items != null && items.isEmpty) ...[
              const SizedBox(height: 24),
              const EmptyView(
                icon: Icons.notifications_none,
                title: 'No notifications yet',
              ),
            ],
            if (items != null)
              for (final item in items) ...[
                const SizedBox(height: 8),
                _NotificationTile(
                  item: item,
                  onTap: () => _markRead(item),
                ),
              ],
          ],
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item, required this.onTap});

  final StarNotification item;
  final VoidCallback onTap;

  static const _categoryIcons = {
    'procedure_submitted': Icons.send_outlined,
    'procedure_approved': Icons.check_circle_outline,
    'procedure_returned': Icons.undo,
    'placement_update': Icons.school_outlined,
    'examiner_assigned': Icons.person_add_alt_1_outlined,
    'assessment_submitted': Icons.fact_check_outlined,
    'assessment_result': Icons.grade_outlined,
    'assessment_correction': Icons.edit_note_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final unread = !item.isRead;
    final accent = unread ? StarColors.primary : StarColors.textInverseMuted;
    return InkWell(
      onTap: onTap,
      child: StarGlass(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(_categoryIcons[item.category] ?? Icons.notifications_outlined,
                color: accent),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: theme.textTheme.bodyLarge?.copyWith(
                      fontWeight: unread ? FontWeight.bold : FontWeight.w400,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.body,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: StarColors.textInverseMuted),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _relativeTime(item.createdAt),
                    style: theme.textTheme.labelSmall
                        ?.copyWith(color: StarColors.textInverseMuted),
                  ),
                ],
              ),
            ),
            if (unread)
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: Icon(Icons.circle, size: 10, color: StarColors.primary),
              ),
          ],
        ),
      ),
    );
  }

  String _relativeTime(String iso) {
    final parsed = DateTime.tryParse(iso);
    if (parsed == null) return iso;
    final diff = DateTime.now().difference(parsed);
    final minutes = diff.inMinutes;
    if (minutes < 1) return 'just now';
    if (minutes < 60) return '${minutes}m ago';
    if (minutes < 1440) return '${diff.inHours}h ago';
    if (minutes < 43200) return '${diff.inDays}d ago';
    return _shortDate(parsed);
  }

  String _shortDate(DateTime date) =>
      '${date.year}-${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
}

/// Category switches (in-app) shown in a modal bottom sheet.
class _PreferencesSheet extends StatefulWidget {
  const _PreferencesSheet({required this.initial, required this.repository});

  final List<NotificationPreference> initial;
  final NotificationsRepository repository;

  @override
  State<_PreferencesSheet> createState() => _PreferencesSheetState();
}

class _PreferencesSheetState extends State<_PreferencesSheet> {
  late final Map<String, NotificationPreference> _prefs;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _prefs = {
      for (final pref in widget.initial) pref.category: pref,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Notification preferences'),
          const SizedBox(height: 12),
          if (_error != null) ...[
            ErrorNotice(message: _error!),
            const SizedBox(height: 8),
          ],
          for (final category in _prefs.keys.toList()..sort())
            SwitchListTile(
              title: Text(_labelFor(category)),
              subtitle: Text(category),
              value: _prefs[category]!.inApp,
              onChanged: _saving
                  ? null
                  : (value) => setState(() =>
                      _prefs[category] = _prefs[category]!.copyWith(inApp: value)),
            ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save preferences'),
          ),
        ],
      ),
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await widget.repository.updatePreferences(_prefs.values.toList());
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = error.friendlyMessage;
        });
      }
    }
  }

  String _labelFor(String category) {
    switch (category) {
      case 'procedure_submitted':
        return 'Record submitted for review';
      case 'procedure_approved':
        return 'Record approved';
      case 'procedure_returned':
        return 'Record returned for correction';
      case 'placement_update':
        return 'Training placement update';
      case 'examiner_assigned':
        return 'Examiner assignment';
      case 'assessment_submitted':
        return 'Assessment awaiting decision';
      case 'assessment_result':
        return 'Assessment decision';
      case 'assessment_correction':
        return 'Assessment corrections requested';
      default:
        return category;
    }
  }
}
