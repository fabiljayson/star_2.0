import 'package:flutter_test/flutter_test.dart';
import 'package:star_mobile/features/legal/legal_models.dart';
import 'package:star_mobile/features/legal/legal_strings.dart';

void main() {
  group('sectionsOf', () {
    test('splits on level-two headings and keeps preamble out', () {
      final sections = sectionsOf(
        'Intro line.\n\n## 1. Acceptance\n\nBy using STAR you agree.\n\n'
        '## 2. Data\n\n- We store records.\n- You can export them.',
      );

      expect(sections.map((section) => section.heading), [
        '1. Acceptance',
        '2. Data',
      ]);
      expect(sections.first.body, 'By using STAR you agree.');
      expect(sections.last.body, contains('You can export them.'));
    });

    test('gives duplicate headings unique slugs', () {
      final sections = sectionsOf('## Scope\n\nA\n\n## Scope\n\nB');
      expect(sections.length, 2);
      expect(sections[0].id, isNot(sections[1].id));
    });

    test('returns nothing for untitled text', () {
      expect(sectionsOf('Just prose without a heading.'), isEmpty);
    });
  });

  group('PolicyDetail.fromJson', () {
    test('reads the public payload including the translation link', () {
      final detail = PolicyDetail.fromJson({
        'policy_slug': 'terms-of-service',
        'language': 'fr',
        'version': '3',
        'title': "Conditions d'utilisation",
        'body': '## 1. Acceptation\n\nTexte.',
        'status': 'published',
        'effective_date': '2026-11-01',
        'published_at': '2026-10-20T10:00:00Z',
        'translation_of': {'language': 'en', 'version': '3'},
      });

      expect(detail.slug, 'terms-of-service');
      expect(detail.language, 'fr');
      expect(detail.version, '3');
      expect(detail.effectiveDate, '2026-11-01');
      expect(detail.translationOf?.language, 'en');
    });
  });

  group('labels', () {
    test('maps policy categories to readable labels', () {
      expect(categoryLabel('privacy'), 'Privacy');
      expect(categoryLabel('marketplace'), 'Marketplace');
    });

    test('formats dates in both languages', () {
      expect(formatLegalDate('2026-11-01', 'en'), '1 Nov 2026');
      expect(formatLegalDate('2026-11-01', 'fr'), '1 nov. 2026');
      expect(formatLegalDate(null, 'en'), '—');
    });

    test('falls back to English strings', () {
      expect(LegalStrings.forLanguage('en').title, 'Policies & Legal');
      expect(LegalStrings.forLanguage('fr').title, contains('légales'));
      expect(LegalStrings.forLanguage('de').title, 'Policies & Legal');
    });
  });
}
