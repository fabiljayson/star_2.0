import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';

/// Second step of the login flow: enter the TOTP code.
class MfaPage extends StatefulWidget {
  const MfaPage({super.key});

  @override
  State<MfaPage> createState() => _MfaPageState();
}

class _MfaPageState extends State<MfaPage> {
  final _codeController = TextEditingController(text: '');
  bool _submitting = false;
  String? _fieldError;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) {
      setState(() => _fieldError = 'Enter the 6-digit code.');
      return;
    }
    setState(() {
      _submitting = true;
      _fieldError = null;
    });
    try {
      await context.read<AppSession>().verifyMfa(code);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _fieldError = error.friendlyMessage);
    } catch (_) {
      if (!mounted) return;
      setState(() => _fieldError = 'Cannot reach the server. Try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              shrinkWrap: true,
              children: [
                const Icon(Icons.shield_outlined, size: 56, color: StarColors.primary),
                const SizedBox(height: 16),
                Text(
                  'Two-factor verification',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                Text(
                  'Enter the 6-digit code from your authenticator app.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: StarColors.textInverseMuted,
                      ),
                ),
                const SizedBox(height: 32),
                StarGlass(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextFormField(
                        controller: _codeController,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        autofocus: true,
                        style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                              letterSpacing: 12,
                            ),
                        textAlign: TextAlign.center,
                        decoration: const InputDecoration(
                          counterText: '',
                          labelText: 'Code',
                          hintText: '000000',
                        ),
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: 16),
                      if (_fieldError != null) ...[
                        ErrorNotice(message: _fieldError!),
                        const SizedBox(height: 12),
                      ],
                      FilledButton(
                        onPressed: _submitting ? null : _submit,
                        child: _submitting
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Verify'),
                      ),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: () {
                          context.read<AppSession>().cancelMfa();
                          if (mounted) {
                            Navigator.of(context).popUntil(
                              (route) => route.isFirst,
                            );
                          }
                        },
                        child: const Text('Back to sign in'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
