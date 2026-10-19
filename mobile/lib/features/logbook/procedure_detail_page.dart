import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'procedure.dart';

/// Detail of one surgical record: full fields + lifecycle actions.
class ProcedureDetailPage extends StatefulWidget {
  const ProcedureDetailPage({super.key, required this.procedureId});
  final String procedureId;

  @override
  State<ProcedureDetailPage> createState() => _ProcedureDetailPageState();
}

class _ProcedureDetailPageState extends State<ProcedureDetailPage> {
  Procedure? _procedure;
  bool _loading = true;
  bool _working = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await context
          .read<AppSession>()
          .api
          .getJson('procedures/${widget.procedureId}/');
      setState(() => _procedure = Procedure.fromJson(
        (data as Map).cast<String, dynamic>(),
      ));
    } on ApiException catch (error) {
      setState(() => _error = error.friendlyMessage);
    } catch (error) {
      setState(() => _error = 'Network problem: $error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submitForReview() async {
    final procedure = _procedure;
    if (procedure == null || _working) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: StarColors.canvas,
        title: const Text('Submit for review?'),
        content: const Text(
          'The record becomes read-only until a reviewer approves it '
          'or sends it back for corrections.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Submit'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    if (!mounted) return;
    setState(() => _working = true);
    try {
      final api = context.read<AppSession>().api;
      final data = await api.postJson('procedures/${widget.procedureId}/submit/');
      if (mounted) {
        setState(() => _procedure = Procedure.fromJson(
          (data as Map).cast<String, dynamic>(),
        ));
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Record submitted for review.')));
      }
    } on ApiException catch (error) {
      if (mounted) showError(context, error);
    } catch (error) {
      if (mounted) showError(context, error);
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final procedure = _procedure;
    final canSubmit = procedure != null &&
        (procedure.status == 'draft' || procedure.status == 'returned');
    return Scaffold(
      appBar: AppBar(
        title: Text(procedure?.reference ?? 'Record'),
        actions: [
          if (procedure != null)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Center(child: StatusBadge(status: procedure.status)),
            ),
        ],
      ),
      floatingActionButton: canSubmit
          ? FloatingActionButton.extended(
              onPressed: _working ? null : _submitForReview,
              icon: _working
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send_outlined),
              label: const Text('Submit'),
            )
          : null,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : procedure == null
                  ? const EmptyView(icon: Icons.search_off, title: 'Record not found')
                  : _buildBody(context, procedure),
    );
  }

  Widget _buildBody(BuildContext context, Procedure procedure) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        StarGlass(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                procedure.procedureName,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  StatusBadge(status: procedure.status),
                  if (procedure.patientReferenceCode != null)
                    _MetaChip(
                      icon: Icons.badge_outlined,
                      label: 'PR ${procedure.patientReferenceCode!}',
                    ),
                  if (procedure.departmentName != null)
                    _MetaChip(
                        icon: Icons.local_hospital_outlined,
                        label: procedure.departmentName!),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _Field(title: 'Date', value: procedure.procedureDate),
        _Field(title: 'Category', value: procedure.category),
        _Field(title: 'Indication', value: procedure.indication),
        _Field(title: 'Summary', value: procedure.summary),
        if (procedure.author != null)
          _Field(title: 'Author', value: procedure.author!.fullName),
        _Field(title: 'Version', value: 'v${procedure.version}'),
        const SizedBox(height: 8),
      ],
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: StarColors.glassHighlight,
        borderRadius: BorderRadius.circular(StarColors.radiusPill),
        border: Border.all(color: StarColors.glassRim),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: StarColors.textInverseMuted),
          const SizedBox(width: 4),
          Text(label, style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({required this.title, required this.value});
  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title.toUpperCase(),
            style: const TextStyle(
              color: StarColors.textInverseMuted,
              fontSize: 11,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.1,
            ),
          ),
          const SizedBox(height: 2),
          SelectableText(value.isEmpty ? '—' : value),
        ],
      ),
    );
  }
}
