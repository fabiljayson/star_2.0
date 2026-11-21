/// Feature-local EN/FR copy for the legal screens.
///
/// The app has no localization framework yet; these strings live with the
/// feature following the existing pattern of English-only copy elsewhere.
class LegalStrings {
  const LegalStrings({
    required this.title,
    required this.subtitle,
    required this.policies,
    required this.consents,
    required this.privacy,
    required this.history,
    required this.version,
    required this.effective,
    required this.published,
    required this.notPublished,
    required this.accept,
    required this.accepted,
    required this.withdraw,
    required this.withdrawn,
    required this.needsAcceptance,
    required this.upToDate,
    required this.consentHistory,
    required this.privacyIntro,
    required this.requestType,
    required this.messageLabel,
    required this.submitRequest,
    required this.requestSubmitted,
    required this.noRequests,
    required this.noConsents,
    required this.retry,
    required this.loadFailed,
    required this.staleNotice,
    required this.draftNotice,
    required this.termsUpdateTitle,
    required this.termsUpdateBody,
    required this.reviewTerms,
    required this.later,
    required this.requiredBeforeContinuing,
    required this.backToList,
    required this.privacyKinds,
  });

  final String title;
  final String subtitle;
  final String policies;
  final String consents;
  final String privacy;
  final String history;
  final String version;
  final String effective;
  final String published;
  final String notPublished;
  final String accept;
  final String accepted;
  final String withdraw;
  final String withdrawn;
  final String needsAcceptance;
  final String upToDate;
  final String consentHistory;
  final String privacyIntro;
  final String requestType;
  final String messageLabel;
  final String submitRequest;
  final String requestSubmitted;
  final String noRequests;
  final String noConsents;
  final String retry;
  final String loadFailed;
  final String staleNotice;
  final String draftNotice;
  final String termsUpdateTitle;
  final String termsUpdateBody;
  final String reviewTerms;
  final String later;
  final String requiredBeforeContinuing;
  final String backToList;
  final Map<String, String> privacyKinds;

  static LegalStrings forLanguage(String language) =>
      language == 'fr' ? french : english;

  static const english = LegalStrings(
    title: 'Policies & Legal',
    subtitle:
        'How STAR handles your account, clinical data, payments and privacy.',
    policies: 'Policies',
    consents: 'Your consents',
    privacy: 'Privacy requests',
    history: 'Version history',
    version: 'Version',
    effective: 'Effective',
    published: 'Published',
    notPublished: 'Not yet published',
    accept: 'Accept',
    accepted: 'Accepted',
    withdraw: 'Withdraw',
    withdrawn: 'Withdrawn',
    needsAcceptance: 'Acceptance needed',
    upToDate: 'Up to date',
    consentHistory: 'Consent history',
    privacyIntro:
        'Ask for a copy, correction or deletion of your personal data. '
        'Requests are reviewed by the STAR team.',
    requestType: 'Request type',
    messageLabel: 'What should we know?',
    submitRequest: 'Submit request',
    requestSubmitted: 'Request received.',
    noRequests: 'No privacy requests yet.',
    noConsents: 'No consents recorded yet.',
    retry: 'Retry',
    loadFailed: 'Could not load this content.',
    staleNotice: 'Showing the last downloaded copy. Reconnect to refresh.',
    draftNotice:
        'Draft text. This version is not published and is not a binding policy.',
    termsUpdateTitle: 'Terms have been updated',
    termsUpdateBody:
        'Please review and accept the current Terms of Service to keep using '
        'marketplace features.',
    reviewTerms: 'Review terms',
    later: 'Later',
    requiredBeforeContinuing: 'Acceptance is required before continuing.',
    backToList: 'All policies',
    privacyKinds: {
      'access': 'Access my data',
      'export': 'Export my data',
      'deletion': 'Delete my data',
      'correction': 'Correct my data',
      'other': 'Other request',
    },
  );

  static const french = LegalStrings(
    title: 'Politiques et mentions légales',
    subtitle:
        'Comment STAR traite votre compte, vos données cliniques, vos '
        'paiements et votre vie privée.',
    policies: 'Politiques',
    consents: 'Vos consentements',
    privacy: 'Demandes relatives à la vie privée',
    history: 'Historique des versions',
    version: 'Version',
    effective: "En vigueur le",
    published: 'Publiée le',
    notPublished: 'Pas encore publiée',
    accept: 'Accepter',
    accepted: 'Acceptée',
    withdraw: 'Retirer',
    withdrawn: 'Retiré',
    needsAcceptance: 'Acceptation requise',
    upToDate: 'À jour',
    consentHistory: 'Historique des consentements',
    privacyIntro:
        'Demandez une copie, une correction ou la suppression de vos données '
        'personnelles. Les demandes sont examinées par l’équipe STAR.',
    requestType: 'Type de demande',
    messageLabel: 'Précisions utiles',
    submitRequest: 'Envoyer la demande',
    requestSubmitted: 'Demande reçue.',
    noRequests: 'Aucune demande pour le moment.',
    noConsents: 'Aucun consentement enregistré.',
    retry: 'Réessayer',
    loadFailed: 'Impossible de charger ce contenu.',
    staleNotice:
        'Affichage de la dernière copie téléchargée. Reconnectez-vous pour '
        'actualiser.',
    draftNotice:
        'Texte provisoire. Cette version n’est pas publiée et ne constitue '
        'pas une politique opposable.',
    termsUpdateTitle: 'Les conditions ont été mises à jour',
    termsUpdateBody:
        'Veuillez consulter et accepter les Conditions d’utilisation en '
        'vigueur pour continuer à utiliser la place de marché.',
    reviewTerms: 'Consulter les conditions',
    later: 'Plus tard',
    requiredBeforeContinuing: 'L’acceptation est requise pour continuer.',
    backToList: 'Toutes les politiques',
    privacyKinds: {
      'access': 'Accéder à mes données',
      'export': 'Exporter mes données',
      'deletion': 'Supprimer mes données',
      'correction': 'Corriger mes données',
      'other': 'Autre demande',
    },
  );
}

String formatLegalDate(String? iso, String language) {
  if (iso == null || iso.isEmpty) return '—';
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) return iso;
  const monthsEn = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  const monthsFr = [
    'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
    'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
  ];
  final months = language == 'fr' ? monthsFr : monthsEn;
  final local = parsed.toLocal();
  return '${local.day} ${months[local.month - 1]} ${local.year}';
}
