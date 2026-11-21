import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'legal_models.dart';
import 'legal_repository.dart';
import 'legal_strings.dart';

/// GDPR-style data requests: submit one, then follow the admin response.
class PrivacyRequestsPage extends StatefulWidget {
  const PrivacyRequestsPage({
    super.key,
    required this.repository,
    required this.strings,
  });

  final LegalRepository repository;
  final LegalStrings strings;

  @override
  State<PrivacyRequestsPage> createState() => _PrivacyRequestsPageState();
}

class _PrivacyRequestsPageState extends State<PrivacyRequestsPage> {
  final _messageController = TextEditingController();
  String _kind = 'access';
  List<PrivacyRequestItem>? _items;
  Object? _error;
  bool _submitting = false;
  String? _formError;

  LegalStrings get _t => widget.strings;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final items = await widget.repository.privacyRequests();
      if (!mounted) return;
      setState(() {
        _items = items;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error);
    }
  }

  Future<void> _submit() async {
    final message = _messageController.text.trim();
    if (message.length < 10) {
      setState(() => _formError = _t.messageLabel);
      return;
    }
    setState(() {
      _submitting = true;
      _formError = null;
    });
    try {
      await widget.repository.openPrivacyRequest(kind: _kind, message: message);
      if (!mounted) return;
      _messageController.clear();
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(_t.requestSubmitted)));
    } catch (error) {
      if (mounted) {
        setState(() => _formError =
            error is ApiException ? error.friendlyMessage : _t.loadFailed);
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_t.privacy)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(_t.privacyIntro),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: _kind,
                    decoration: InputDecoration(labelText: _t.requestType),
                    items: [
                      for (final entry in _t.privacyKinds.entries)
                        DropdownMenuItem(
                          value: entry.key,
                          child: Text(entry.value),
                        ),
                    ],
                    onChanged: (value) =>
                        setState(() => _kind = value ?? _kind),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _messageController,
                    minLines: 4,
                    maxLines: 8,
                    maxLength: 2000,
                    decoration: InputDecoration(
                      labelText: _t.messageLabel,
                      alignLabelWithHint: true,
                    ),
                  ),
                  if (_formError != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      _formError!,
                      style: const TextStyle(color: StarColors.danger),
                    ),
                  ],
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton(
                      onPressed: _submitting ? null : _submit,
                      child: _submitting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(_t.submitRequest),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          _requests(),
        ],
      ),
    );
  }

  Widget _requests() {
    if (_error != null && _items == null) {
      return ErrorView(
        message: _error is ApiException
            ? (_error as ApiException).friendlyMessage
            : _t.loadFailed,
        onRetry: _load,
      );
    }
    final items = _items;
    if (items == null) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (items.isEmpty) {
      return EmptyView(icon: Icons.inbox_outlined, title: _t.noRequests);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final item in items)
          Card(
            child: ListTile(
              title: Text(item.kindLabel),
              subtitle: Text([
                item.status,
                if (item.createdAt != null) formatLegalDate(item.createdAt, 'en'),
                if (item.responseNote.isNotEmpty) item.responseNote,
              ].join(' · ')),
              trailing: StatusBadge(status: item.status),
            ),
          ),
      ],
    );
  }
}
