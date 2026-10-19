import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'logbook_repository.dart';
import 'procedure.dart';

/// Minimal draft creator matching the API contract of `procedures/` POST.
class ProcedureCreatePage extends StatefulWidget {
  const ProcedureCreatePage({super.key});

  @override
  State<ProcedureCreatePage> createState() => _ProcedureCreatePageState();
}

class _ProcedureCreatePageState extends State<ProcedureCreatePage> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _dateController = TextEditingController();
  final _indicationController = TextEditingController();
  final _summaryController = TextEditingController();
  String _category = 'elective';
  bool _saving = false;
  String? _formError;

  static const _categories = {
    'elective': 'Elective',
    'emergency': 'Emergency',
    'urgent': 'Urgent',
    'trauma': 'Trauma',
  };

  @override
  void dispose() {
    _nameController.dispose();
    _dateController.dispose();
    _indicationController.dispose();
    _summaryController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: DateTime(now.year - 15),
      lastDate: now,
      builder: (context, child) => Theme(
        data: Theme.of(context).copyWith(
          colorScheme: Theme.of(context).colorScheme.copyWith(
                primary: StarColors.primary,
                surface: StarColors.canvas,
              ),
        ),
        child: child!,
      ),
    );
    if (picked == null) return;
    setState(() {
      _dateController.text =
          '${picked.year.toString().padLeft(4, '0')}-'
          '${picked.month.toString().padLeft(2, '0')}-'
          '${picked.day.toString().padLeft(2, '0')}';
    });
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final session = context.read<AppSession>();
    final user = session.user;
    final institution = _firstInstitutionId(user);
    if (institution == null) {
      setState(() => _formError =
          'Your account is not linked to an institution represented in this build.');
      return;
    }
    setState(() {
      _saving = true;
      _formError = null;
    });
    try {
      final repo = LogbookRepository(session);
      final procedure = await repo.create(ProcedureCreateInput(
        institutionId: institution,
        procedureDate: _dateController.text,
        category: _category,
        procedureName: _nameController.text.trim(),
        indication: _indicationController.text.trim(),
        summary: _summaryController.text.trim(),
      ));
      if (mounted) {
        Navigator.of(context).pop(procedure);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Draft ${procedure.reference} created.'),
        ));
      }
    } on ApiException catch (error) {
      setState(() => _formError = error.friendlyMessage);
    } catch (error) {
      setState(
        () => _formError = 'Cannot reach the server. Check your connection.',
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _firstInstitutionId(StarUser? user) {
    final roles = user?.roles ?? const [];
    for (final role in roles) {
      final institution = role['institution'];
      if (institution is Map<String, dynamic>) return '${institution['id']}';
      if (institution != null) return '$institution';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New surgical record')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_formError != null) ...[
              ErrorNotice(message: _formError!),
              const SizedBox(height: 16),
            ],
            TextFormField(
              controller: _nameController,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: 'Procedure name'),
              validator: (value) =>
                  value == null || value.trim().isEmpty ? 'Required.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _dateController,
              readOnly: true,
              onTap: _pickDate,
              decoration: const InputDecoration(
                labelText: 'Procedure date',
                suffixIcon: Icon(Icons.calendar_today_outlined),
              ),
              validator: (value) =>
                  value == null || value.isEmpty ? 'Pick a date.' : null,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _category,
              decoration: const InputDecoration(labelText: 'Category'),
              items: [
                for (final entry in _categories.entries)
                  DropdownMenuItem(value: entry.key, child: Text(entry.value)),
              ],
              onChanged: (value) =>
                  setState(() => _category = value ?? 'elective'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _indicationController,
              textInputAction: TextInputAction.next,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Indication'),
              validator: (value) =>
                  value == null || value.trim().isEmpty ? 'Required.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _summaryController,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(labelText: 'Operative summary'),
              validator: (value) =>
                  value == null || value.trim().isEmpty ? 'Required.' : null,
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save draft'),
            ),
          ],
        ),
      ),
    );
  }
}
