import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_session.dart';
import '../../theme.dart';
import 'legal_repository.dart';
import 'legal_strings.dart';
import 'policy_detail_page.dart';

const termsPolicySlug = 'terms-of-service';

/// Non-blocking notice shown when the account has not accepted the current
/// Terms of Service version. Marketplace writes stay blocked server-side
/// until it is accepted.
class TermsUpdateBanner extends StatefulWidget {
  const TermsUpdateBanner({super.key});

  @override
  State<TermsUpdateBanner> createState() => _TermsUpdateBannerState();
}

class _TermsUpdateBannerState extends State<TermsUpdateBanner> {
  bool _dismissed = false;

  @override
  Widget build(BuildContext context) {
    final session = context.watch<AppSession>();
    final user = session.user;
    if (user == null || !user.requiresTermsAcceptance || _dismissed) {
      return const SizedBox.shrink();
    }
    final language =
        Localizations.localeOf(context).languageCode == 'fr' ? 'fr' : 'en';
    final strings = LegalStrings.forLanguage(language);

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: StarColors.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(StarColors.radiusMd),
        border: Border.all(color: StarColors.warning.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.gavel_outlined,
                  size: 18, color: StarColors.warning),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  strings.termsUpdateTitle,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                tooltip: strings.later,
                onPressed: () => setState(() => _dismissed = true),
                icon: const Icon(Icons.close, size: 18),
              ),
            ],
          ),
          Text(
            strings.termsUpdateBody,
            style: const TextStyle(color: StarColors.textInverseMuted),
          ),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.tonal(
              onPressed: () async {
                await Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => PolicyDetailPage(
                    repository: LegalRepository(session),
                    slug: termsPolicySlug,
                    language: language,
                  ),
                ));
                if (!context.mounted) return;
                await session.refreshUser();
              },
              child: Text(strings.reviewTerms),
            ),
          ),
        ],
      ),
    );
  }
}
