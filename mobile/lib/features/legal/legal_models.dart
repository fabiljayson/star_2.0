/// Typed view of the backend Policies & Legal Center payloads.
class PublishedVersionBrief {
  PublishedVersionBrief({
    required this.language,
    required this.version,
    required this.effectiveDate,
  });

  final String language;
  final String version;
  final String? effectiveDate;

  factory PublishedVersionBrief.fromJson(Map<String, dynamic> json) =>
      PublishedVersionBrief(
        language: '${json['language'] ?? 'en'}',
        version: '${json['version'] ?? ''}',
        effectiveDate: json['effective_date'] as String?,
      );
}

class PolicySummary {
  PolicySummary({
    required this.slug,
    required this.title,
    required this.category,
    required this.summary,
    required this.publishedVersions,
  });

  final String slug;
  final String title;
  final String category;
  final String summary;
  final List<PublishedVersionBrief> publishedVersions;

  bool get hasPublishedText => publishedVersions.isNotEmpty;

  factory PolicySummary.fromJson(Map<String, dynamic> json) => PolicySummary(
        slug: '${json['slug']}',
        title: '${json['title'] ?? ''}',
        category: '${json['category'] ?? ''}',
        summary: '${json['summary'] ?? ''}',
        publishedVersions: (json['published_versions'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(PublishedVersionBrief.fromJson)
            .toList(),
      );
}

class PolicyTranslation {
  PolicyTranslation({required this.language, required this.version});

  final String language;
  final String version;

  factory PolicyTranslation.fromJson(Map<String, dynamic> json) =>
      PolicyTranslation(
        language: '${json['language'] ?? ''}',
        version: '${json['version'] ?? ''}',
      );
}

class PolicyDetail {
  PolicyDetail({
    required this.slug,
    required this.language,
    required this.version,
    required this.title,
    required this.body,
    required this.status,
    required this.effectiveDate,
    required this.publishedAt,
    required this.translationOf,
  });

  final String slug;
  final String language;
  final String version;
  final String title;
  final String body;
  final String status;
  final String? effectiveDate;
  final String? publishedAt;
  final PolicyTranslation? translationOf;

  factory PolicyDetail.fromJson(Map<String, dynamic> json) => PolicyDetail(
        slug: '${json['policy_slug'] ?? ''}',
        language: '${json['language'] ?? 'en'}',
        version: '${json['version'] ?? ''}',
        title: '${json['title'] ?? ''}',
        body: '${json['body'] ?? ''}',
        status: '${json['status'] ?? ''}',
        effectiveDate: json['effective_date'] as String?,
        publishedAt: json['published_at'] as String?,
        translationOf: json['translation_of'] is Map<String, dynamic>
            ? PolicyTranslation.fromJson(
                json['translation_of'] as Map<String, dynamic>)
            : null,
      );
}

class PolicyHistoryItem {
  PolicyHistoryItem({
    required this.version,
    required this.status,
    required this.publishedAt,
    required this.effectiveDate,
  });

  final String version;
  final String status;
  final String? publishedAt;
  final String? effectiveDate;

  factory PolicyHistoryItem.fromJson(Map<String, dynamic> json) =>
      PolicyHistoryItem(
        version: '${json['version'] ?? ''}',
        status: '${json['status'] ?? ''}',
        publishedAt: json['published_at'] as String?,
        effectiveDate: json['effective_date'] as String?,
      );
}

class ConsentStatusItem {
  ConsentStatusItem({
    required this.policy,
    required this.title,
    required this.currentVersion,
    required this.consentCurrent,
  });

  final String policy;
  final String title;
  final String currentVersion;
  final bool consentCurrent;

  factory ConsentStatusItem.fromJson(Map<String, dynamic> json) =>
      ConsentStatusItem(
        policy: '${json['policy']}',
        title: '${json['title'] ?? ''}',
        currentVersion: '${json['current_version'] ?? ''}',
        consentCurrent: json['consent_current'] == true,
      );
}

class ConsentRecord {
  ConsentRecord({
    required this.id,
    required this.policySlug,
    required this.policyTitle,
    required this.version,
    required this.context,
    required this.withdrawnAt,
    required this.createdAt,
  });

  final String id;
  final String policySlug;
  final String policyTitle;
  final String version;
  final String context;
  final String? withdrawnAt;
  final String? createdAt;

  factory ConsentRecord.fromJson(Map<String, dynamic> json) => ConsentRecord(
        id: '${json['id']}',
        policySlug: '${json['policy_slug']}',
        policyTitle: '${json['policy_title'] ?? ''}',
        version: '${json['version'] ?? ''}',
        context: '${json['context'] ?? ''}',
        withdrawnAt: json['withdrawn_at'] as String?,
        createdAt: json['created_at'] as String?,
      );
}

class PrivacyRequestItem {
  PrivacyRequestItem({
    required this.id,
    required this.kind,
    required this.kindLabel,
    required this.status,
    required this.responseNote,
    required this.createdAt,
    required this.handledAt,
  });

  final String id;
  final String kind;
  final String kindLabel;
  final String status;
  final String responseNote;
  final String? createdAt;
  final String? handledAt;

  factory PrivacyRequestItem.fromJson(Map<String, dynamic> json) =>
      PrivacyRequestItem(
        id: '${json['id']}',
        kind: '${json['kind']}',
        kindLabel: '${json['kind_label'] ?? json['kind'] ?? ''}',
        status: '${json['status'] ?? ''}',
        responseNote: '${json['response_note'] ?? ''}',
        createdAt: json['created_at'] as String?,
        handledAt: json['handled_at'] as String?,
      );
}

/// One `## heading` block of a policy body, used for the in-page table of
/// contents exactly like the web client.
class PolicySection {
  PolicySection({required this.id, required this.heading, required this.body});

  final String id;
  final String heading;
  final String body;
}

List<PolicySection> sectionsOf(String body) {
  final sections = <PolicySection>[];
  final used = <String>{};
  String? heading;
  final buffer = <String>[];

  void flush() {
    if (heading == null) return;
    var id = _slugify(heading);
    var n = 2;
    while (used.contains(id)) {
      id = '${_slugify(heading)}-${n++}';
    }
    used.add(id);
    sections.add(PolicySection(
      id: id,
      heading: heading,
      body: buffer.join('\n').trim(),
    ));
  }

  for (final line in body.split('\n')) {
    if (line.startsWith('## ')) {
      flush();
      heading = line.substring(3).trim();
      buffer.clear();
    } else if (heading != null) {
      buffer.add(line);
    }
  }
  flush();
  return sections;
}

String _slugify(String heading) => heading
    .toLowerCase()
    .replaceAll(RegExp(r'[^a-z0-9]+'), '-')
    .replaceAll(RegExp(r'^-+|-+$'), '');

String categoryLabel(String category) {
  switch (category) {
    case 'privacy':
      return 'Privacy';
    case 'terms':
      return 'Terms of Service';
    case 'marketplace':
      return 'Marketplace';
    case 'payments':
      return 'Subscription & payments';
    case 'clinical':
      return 'Clinical data';
    case 'data_retention':
      return 'Cookies & data retention';
    default:
      return category;
  }
}

String statusLabel(String status) => status
    .split('_')
    .map((part) => part.isEmpty
        ? part
        : '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');
