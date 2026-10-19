import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persisted shape of a signed-in session.
class StoredSession {
  StoredSession({
    required this.accessToken,
    required this.refreshToken,
    required this.user,
  });

  final String accessToken;
  final String refreshToken;
  final Map<String, dynamic> user;

  factory StoredSession.fromJson(Map<String, dynamic> json) => StoredSession(
        accessToken: json['access'] as String,
        refreshToken: json['refresh'] as String,
        user: json['user'] as Map<String, dynamic>,
      );

  Map<String, dynamic> toJson() => {
        'access': accessToken,
        'refresh': refreshToken,
        'user': user,
      };
}

/// Key-value persistence for the session blob (and free-form small data).
abstract class SecureKeyValueStore {
  Future<String?> readValue(String key);
  Future<void> writeValue(String key, String? value);
}

/// Encrypted-on-disk implementation backed by flutter_secure_storage.
class PlatformSecureStore implements SecureKeyValueStore {
  PlatformSecureStore() : _storage = const FlutterSecureStorage(
          aOptions: AndroidOptions(),
        );

  final FlutterSecureStorage _storage;

  @override
  Future<String?> readValue(String key) => _storage.read(key: key);

  @override
  Future<void> writeValue(String key, String? value) => value == null
      ? _storage.delete(key: key)
      : _storage.write(key: key, value: value);
}

/// In-memory implementation for tests and no-persistence mode.
class MemorySecureStore implements SecureKeyValueStore {
  final Map<String, String> _values = {};

  @override
  Future<String?> readValue(String key) async => _values[key];

  @override
  Future<void> writeValue(String key, String? value) async {
    if (value == null) {
      _values.remove(key);
    } else {
      _values[key] = value;
    }
  }
}

const sessionStorageKey = 'star.stored_session';
const serverUrlStorageKey = 'star.server_url';
const onboardingDoneKey = 'star.onboarding_done';

class SessionStore {
  SessionStore({required this.storage, this.maximumSessions = 1});

  final SecureKeyValueStore storage;
  final int maximumSessions;

  Future<StoredSession?> load() async {
    final raw = await storage.readValue(sessionStorageKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      return StoredSession.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } on FormatException {
      return null;
    }
  }

  Future<void> save(StoredSession session) =>
      storage.writeValue(sessionStorageKey, jsonEncode(session.toJson()));

  Future<void> clear() => storage.writeValue(sessionStorageKey, null);

  Future<String?> loadServerUrl() => storage.readValue(serverUrlStorageKey);

  Future<void> saveServerUrl(String? url) =>
      storage.writeValue(serverUrlStorageKey, url);

  /// True only when the first-launch tour was finished (or skipped).
  Future<bool> isOnboardingDone() async {
    final raw = await storage.readValue(onboardingDoneKey);
    return raw == 'done';
  }

  Future<void> markOnboardingDone() =>
      storage.writeValue(onboardingDoneKey, 'done');
}
