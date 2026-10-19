import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/app_session.dart';
import 'core/session_store.dart';
import 'home_shell.dart';
import 'theme.dart';

void main() {
  runApp(const StarMobileApp());
}

/// Composition root.
///
/// Tests replace [SessionStore] (in-memory) and pump their own session, so
/// production wiring is intentionally minimal here.
class StarMobileApp extends StatefulWidget {
  const StarMobileApp({super.key, this.sessionOverride});

  final AppSession? sessionOverride;

  @override
  State<StarMobileApp> createState() => _StarMobileAppState();
}

class _StarMobileAppState extends State<StarMobileApp> {
  late final SessionStore _store;
  late final AppSession _session;

  @override
  void initState() {
    super.initState();
    _store = SessionStore(storage: PlatformSecureStore());
    _session = widget.sessionOverride ?? AppSession(store: _store);
    unawaited(_restoreSession());
  }

  Future<void> _restoreSession() => _session.restore();

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _session,
      child: MaterialApp(
        title: 'STAR',
        debugShowCheckedModeBanner: false,
        theme: buildStarTheme(),
        home: const AuthGate(),
      ),
    );
  }
}
