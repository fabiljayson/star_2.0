import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';

/// Sign-in screen. Completes in one step (email+password) or flips to [MfaPage]
/// when the account has TOTP enabled.
class LoginPage extends StatefulWidget {
  const LoginPage({super.key, this.onAnonymousBootSuccess});
  final VoidCallback? onAnonymousBootSuccess;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController(text: '');
  bool _serverAdvanced = false;
  final _serverController = TextEditingController();
  bool _submitting = false;
  String? _fieldError;

  @override
  void initState() {
    super.initState();
    final session = context.read<AppSession>();
    _serverController.text = session.serverUrl;
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final session = context.read<AppSession>();
    if (session.serverUrl != _serverController.text.trim().replaceFirst(RegExp(r'/*$'), '')) {
      await session.updateServerUrl(_serverController.text);
    }
    setState(() {
      _submitting = true;
      _fieldError = null;
    });
    try {
      await session.login(
        _emailController.text.trim(),
        _passwordController.text,
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _fieldError = error.friendlyMessage);
    } catch (_) {
      if (!mounted) return;
      setState(
        () => _fieldError = 'Cannot reach that server. Check the URL and try again.',
      );
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
                const Icon(Icons.medical_services_outlined,
                    size: 56, color: StarColors.primary),
                const SizedBox(height: 16),
                Text(
                  'STAR',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        letterSpacing: 4,
                        color: StarColors.primary,
                      ),
                ),
                Text(
                  'Surgical tracking & assessment',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: StarColors.textInverseMuted,
                      ),
                ),
                const SizedBox(height: 32),
                StarGlass(
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        TextFormField(
                          controller: _emailController,
                          keyboardType: TextInputType.emailAddress,
                          autofillHints: const [AutofillHints.email],
                          textInputAction: TextInputAction.next,
                          decoration: const InputDecoration(
                            labelText: 'Email',
                            prefixIcon: Icon(Icons.alternate_email),
                          ),
                          validator: (value) => value == null || value.trim().isEmpty
                              ? 'Enter your email.'
                              : null,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _passwordController,
                          obscureText: true,
                          autofillHints: const [AutofillHints.password],
                          onFieldSubmitted: (_) => _submit(),
                          decoration: const InputDecoration(
                            labelText: 'Password',
                            prefixIcon: Icon(Icons.lock_outline),
                          ),
                          validator: (value) => value == null || value.isEmpty
                              ? 'Enter your password.'
                              : null,
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
                              : const Text('Sign in'),
                        ),
                        const SizedBox(height: 12),
                        TextButton(
                          onPressed: () =>
                              setState(() => _serverAdvanced = !_serverAdvanced),
                          child: Text(
                            _serverAdvanced ? 'Hide server settings' : 'Other server…',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: StarColors.textInverseMuted,
                                ),
                          ),
                        ),
                        if (_serverAdvanced)
                          TextFormField(
                            controller: _serverController,
                            keyboardType: TextInputType.url,
                            decoration: const InputDecoration(
                              labelText: 'Server URL',
                              hintText: 'http://192.168.1.10:8002/api/v1',
                              helperText: 'Defaults to 10.0.2.2:8002 (host from emulator).',
                            ),
                          ),
                      ],
                    ),
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
