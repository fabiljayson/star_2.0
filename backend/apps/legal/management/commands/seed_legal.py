# seed_legal.py
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.legal.models import Policy, PolicyVersion

# Catalogue of the Policy Center (stable slugs, bilingual versions).
# Operator-identifying facts are intentionally left as placeholders — the
# students running the platform must fill them in before production use.
OPERATOR = "[[Operator name — to be supplied]]"
CONTACT = "[[contact email — to be supplied]]"

CONTENT: dict[str, dict] = {}


CONTENT["privacy-policy"] = {
    "en": {
        "title": "Privacy Policy",
        "body": f"""## 1. Who this policy covers

This Privacy Policy explains how {OPERATOR} (the "platform") handles
personal information collected through STAR, a digital platform for
surgical documentation, clinical training, and an equipment marketplace
oriented towards Cameroon and its health institutions. It applies to the
web application, the mobile application, and the administrative services.

## 2. Information we collect

STAR deliberately collects as little as possible:

- **Account data**: email address, first and last name, business roles,
  verification status, hashed credentials, multi-factor enrolment state.
- **Clinical data**: surgical logbook entries (procedure, role, date),
  pseudonymised patient references (no names), free-text notes, attachments
  and assessment records related to those entries.
- **Commercial data**: marketplace orders, carts, seller subscriptions,
  invoices and payment status (never full card numbers — payments are
  handled by the payment provider, see the Subscription & Payment policy).
- **Technical data**: request identifiers, IP address, user agent, audit
  trail entries, and coarse error diagnostics.

## 3. Why we process it (purposes)

- Creating and administering accounts, roles and access rights.
- Allowing clinicians and their institutions to document, review and
  assess surgical procedures.
- Operating the marketplace: catalogues, orders, shipping and payments.
- Security, integrity and audit compliance of the platform itself.
- Sending service-related notifications the user has subscribed to.

STAR does **not** sell personal data and does not use clinical logbook
content for advertising.

## 4. On what basis

Account administration rests on the performance of the service contract
(the Terms of Service). Clinical documentation serves the professional
and training purpose chosen by the user and their institution. Payment
records are processed for performance of the purchase contract and for
bookkeeping. Security logs rely on the legitimate interest of protecting
the platform.

## 5. Who can see what

- The user's own data is visible to the user and, where applicable, to
  their reviewing examiner, their institution administrators, and the
  platform administrators who need access for support and audit.
- Marketplace order data is shared between the buyer and the relevant
  seller for fulfilment purposes.
- Suppliers never see the buyer's other orders.
- Access is role-scoped and logged. Administrative access requires
  multi-factor authentication.

## 6. Retention

Account data is retained while the account is active. Clinical logbook
entries belong to their author and are retained for professional record
purposes; pseudonymisation means no patient names are stored. Security
and audit logs are retained for a fixed period defined by the operator
and then periodically purged (see the Cookies & Retention policy). A
deletion request removes or irreversibly anonymises the information not
required for legal bookkeeping.

## 7. Security

Data is encrypted in transit. Passwords are stored using modern adaptive
hashing. Sensitive settings, credentials and secret keys are configured
through environment variables, never in code or logs. Administrative
sessions require MFA. Backups, where configured by the hosting operator,
are access-controlled.

## 8. Your rights

Subject to the law applicable to you, you may ask to access, correct,
export or delete your personal information, and raise objections about
processing. STAR provides a built-in **Privacy requests** workflow
(Settings → Privacy request) that forwards your request to the operator.
You may also use [[contact email — to be supplied]] or the address of the
supervisory authority where applicable.

## 9. International transfers and hosting

Hosting is operated by {OPERATOR}. Details about hosting region and any
transfer of data to third countries are documented by the operator in
this section's placeholder before production use.

## 10. Changes and contact

Material changes to this policy will be announced in the Policy Center,
and significant ones may require renewed agreement. Questions can be
addressed to {CONTACT}.""",
    },
    "fr": {
        "title": "Politique de confidentialité",
        "body": """## 1. À qui s'applique cette politique

Cette politique de confidentialité explique comment [[Opérateur — à
compléter]] (la « plateforme ») traite les informations personnelles
collectées via STAR, plateforme numérique de documentation chirurgicale,
de formation clinique et de marketplace d'équipements orientée vers le
Cameroun et ses établissements de santé. Elle couvre l'application web,
l'application mobile et les services d'administration.

## 2. Informations collectées

STAR ne collecte délibérément que le minimum :

- **Données de compte** : adresse e-mail, prénom, nom, rôles métier,
  statut de vérification, identifiants chiffrés, état de l'authentification
  à deux facteurs.
- **Données cliniques** : entrées du carnet opératoire (intervention,
  rôle, date), références patients pseudonymisées (aucun nom), notes
  libres, pièces jointes et évaluations rattachées à ces entrées.
- **Données commerciales** : commandes, paniers, abonnements vendeur,
  factures et statut de paiement — jamais de numéros de carte complets
  (les paiements sont traités par le prestataire, voir la politique
  « Abonnement, paiement et remboursement »).
- **Données techniques** : identifiants de requête, adresse IP, agent
  utilisateur, entrées du journal d'audit, diagnostics d'erreur sommaires.

## 3. Finalités

- Créer et administrer comptes, rôles et droits d'accès.
- Permettre aux soignants et à leur établissement de documenter, relire
  et évaluer des interventions chirurgicales.
- Exploiter la marketplace : catalogue, commandes, expédition, paiements.
- Assurer la sécurité, l'intégrité et l'auditabilité de la plateforme.
- Envoyer les notifications de service acceptées par l'utilisateur.

STAR ne vend pas de données personnelles et n'utilise pas le contenu des
carnets opératoires à des fins publicitaires.

## 4. Bases de traitement

La gestion du compte repose sur l'exécution du contrat de service (CGU).
La documentation clinique répond à l'objectif professionnel choisi par
l'utilisateur et son établissement. Les enregistrements de paiement sont
traités pour l'exécution du contrat d'achat et les obligations
comptables. Les journaux de sécurité s'appuient sur l'intérêt légitime
de protéger la plateforme.

## 5. Qui voit quoi

- Les données propres d'un utilisateur sont visibles par lui-même et, le
  cas échéant, par son examinateur relais, les administrateurs de son
  établissement, et les administrateurs de la plateforme qui en ont
  besoin pour le support et l'audit.
- Les données de commande sont partagées entre l'acheteur et le vendeur
  concerné pour la bonne exécution.
- Les vendeurs ne voient jamais les autres commandes d'un acheteur.
- Les accès sont restreints par rôle et journalisés. L'accès
  administrateur exige l'authentification à deux facteurs.

## 6. Conservation

Les données de compte sont conservées tant que le compte est actif. Les
entrées du carnet appartiennent à leur auteur et sont conservées pour
les besoins de la trace professionnelle ; la pseudonymisation exclut
tout nom de patient. Les journaux techniques sont conservés pour une
durée fixée par l'opérateur puis purgés (voir la politique « Cookies et
conservation des données »). Une demande de suppression efface ou rend
anonyme de façon irréversible ce qui n'est pas requis par les obligations
comptables.

## 7. Sécurité

Les données sont chiffrées en transit. Les mots de passe sont stockés
avec un hachage adaptatif moderne. Les paramètres sensibles, identifiants
et clés secrètes sont configurés via des variables d'environnement,
jamais dans le code ou les journaux. Les sessions administratives
exigent l'authentification à deux facteurs.

## 8. Vos droits

Sous réserve du droit applicable, vous pouvez demander l'accès, la
correction, l'export ou la suppression de vos informations personnelles
et contester un traitement. STAR fournit un flux intégré de **demandes
de confidentialité** (Réglages → Demande de confidentialité) qui transmet
votre demande à l'opérateur. Vous pouvez aussi utiliser [[e-mail de
contact — à compléter]] ou l'adresse de l'autorité de contrôle si vous y
avez droit.

## 9. Transferts et hébergement

L'hébergement est géré par [[Opérateur — à compléter]]. La région
d'hébergement et tout transfert éventuel vers des pays tiers sont
documentés par l'opérateur dans cette section avant la mise en
production.

## 10. Évolutions et contact

Toute modification substantielle sera annoncée dans le Centre des
politiques et, le cas échéant, une nouvelle acceptation vous sera
demandée. Contact : [[e-mail de contact — à compléter]].""",
    },
}

CONTENT["terms-of-service"] = {
    "en": {
        "title": "Terms of Service",
        "body": f"""## 1. Agreement

These Terms of Service govern the use of STAR by {OPERATOR}. By creating
an account you agree to them. No clause overrides requirements coming
from your institution, your regulator, or mandatory law.

## 2. Accounts, roles and verification

Registration uses your real identity and (where relevant) your
institution affiliation. Clinical roles such as consultant, chief
resident, examiner or institution administrator are granted and revoked
by institution administrators, not by self-registration. Misuse of
another person's identity or institution is grounds for immediate
suspension.

## 3. Acceptable use

You agree, among other things, not to use the platform to:

- document procedures you did not participate in, or fabricate
  assessment outcomes;
- share patient-identifying information; STAR requires pseudonymised
  references;
- upload unlawful, defamatory or infringing content;
- probe, scan or bypass the security mechanisms of the platform;
- circumvent subscription obligations of the marketplace, share
  accounts, or resell access.

## 4. Clinical content, assessments and professional responsibility

Clinical logbooks, procedure records and assessments reflect the
declared practice of licensed professionals. Grades and reviewer
comments follow the training framework of the user's institution.
STAR stores and presents this information; it plays no part in the
medical judgement itself and does not diagnose or treat anything.
The author remains responsible for what they document and certify.

## 5. Marketplace

The marketplace offers surgical equipment from independent verified
suppliers. Orders are a contract between buyer and supplier: the
supplier is responsible for stock, shipment and compliance of the
hardware; STAR operates the platform, escrow of dispute records,
refunds workflow and subscriptions. Prices, currency and payment
rules are described in the marketplace policy listings.

## 6. Subscriptions, fees and closure

Publishing equipment as a seller requires an active seller
subscription. Subscription terms, prices and the sandbox demonstration
flow are governed by the Subscription & Payment policy. We may change
prices prospectively; existing paid periods are never shortened. Users
may close their account at any time; closing does not cancel accrued
payment obligations or legal record-keeping duties.

## 7. Service levels and availability

STAR is offered as a professional documentation tool without uptime
guarantee beyond reasonable care. Maintenance windows, backup
restoration and incident notices are handled by the operator's own
procedures.

## 8. Intellectual property

Documentation, grades and their evidence belong to the operators and
their authors as configured by institutions. Platform code, brand and
interface remain owned by their authors. Users grant STAR the right to
store, display and process their content strictly for operating the
service.

## 9. Termination

Accounts can be suspended for policy violations, security behaviour,
failed identity verification, or institution direction. Record-keeping
obligations of suspended users remain tracked for audit.

## 10. Disclaimers and liability

Nothing on STAR constitutes medical advice, diagnosis or treatment
promise. Hardware descriptions come from their suppliers. To the
maximum extent permitted by law, the operator's aggregate liability
is limited following the rules documented in [[liability limits — to be
supplied by the operator]].

## 11. Governing terms

Operator identity, chosen law, competent courts and consumer-notice
rules must be filled by the operator here. STAR itself does not claim
any jurisdictional authority.""",
    },
    "fr": {
        "title": "Conditions générales d'utilisation",
        "body": """## 1. Convention

Les présentes Conditions générales régissent l'utilisation de STAR par
[[Opérateur — à compléter]]. La création d'un compte vaut acceptation.
Aucune clause ne remplace les règles émanant de l'établissement, du
régulateur ou de la loi.

## 2. Comptes, rôles et vérification

L'inscription repose sur votre identité réelle et (selon le cas) votre
rattachement d'établissement. Les rôles cliniques (chirurgien senior,
interne, examinateur, administrateur d'établissement) sont accordés et
retirés par les administrateurs d'établissement, jamais par
auto-inscription. L'usurpation d'identité ou d'établissement constitue
un motif immédiat de suspension.

## 3. Bon usage

Vous vous engagez notamment à ne pas :

- documenter des interventions auxquelles vous n'avez pas participé ou
  inventer des résultats d'évaluation ;
- partager des informations permettant d'identifier un patient — STAR
  impose des références pseudonymisées ;
- transférer des contenus illicites, diffamatoires ou contrefaisants ;
- sonder, scanner ou contourner les mécanismes de sécurité ;
- contourner la souscription requise du marché des vendeurs, partager
  des comptes ou revendre l'accès.

## 4. Contenus cliniques et responsabilité professionnelle

Les carnets opératoires, fiches d'intervention et évaluations reflètent
la pratique déclarée de professionnels formés. Grilles, notes et
commentaires suivent le cadre de formation de l'établissement de
l'utilisateur. STAR stocke et présente ces informations ; il n'intervient
pas dans le jugement médical lui-même et ne diagnostique ni ne soigne
rien. L'auteur demeure responsable de ce qu'il documente et certifie.

## 5. Marketplace

La marketplace propose des équipements chirurgicaux de fournisseurs
indépendants vérifiés. Une commande établit un contrat entre l'acheteur
et le fournisseur : le fournisseur est responsable du stock, de
l'expédition et de la conformité du matériel ; STAR exploite la
plateforme, le suivi des litiges, le traitement des remboursements et
les abonnements. Prix, devise et règles de paiement figurent dans les
politiques du marketplace.

## 6. Abonnements, frais et clôture

La publication d'équipements comme vendeur requiert un abonnement
vendeur actif. Conditions, tarifs et flux de démonstration sont régis
par la politique « Abonnement, paiement et remboursement ». Les prix
peuvent évoluer ; les périodes déjà payées ne sont jamais raccourcies.
Chacun peut fermer son compte ; la clôture n'annule ni les sommes
déchues ni les obligations de tenue de registres.

## 7. Niveau de service

STAR est proposé comme outil professionnel de documentation, sans
garantie de disponibilité au-delà du soin raisonnable. Fenêtres de
maintenance, restauration de sauvegardes et notifications d'incident
relèvent des procédures de l'opérateur.

## 8. Propriété intellectuelle

Documentation, évaluations et pièces rattachées appartiennent aux
auteurs et opérateurs selon la configuration des établissements. Qui
 confronte le code, la marque et l'interface reviennent à leurs auteurs.
Chaque utilisateur accorde à STAR le droit de conserver, afficher et
traiter ses contenus, strictement pour exploiter le service.

## 9. Résiliation

Les comptes peuvent être suspendus en cas de violation des politiques,
de comportement de sécurité, d'échec de vérification d'identité ou sur
directive de l'établissement. Les obligations de traçabilité des
utilisateurs suspendus restent suivies.

## 10. Exclusions et responsabilité

Rien dans STAR ne vaut avis médical, diagnostic ou promesse de
traitement. Les descriptions matérielles viennent des fournisseurs. Dans
la mesure permise par la loi, la responsabilité globale de l'opérateur
est limitée selon le régime documenté [[règles de responsabilité et
montants — à compléter par l'opérateur]].

## 11. Droit applicable

Identité de l'opérateur, loi choisie, tribunaux compétents et mentions
consuméristes ici à compléter. STAR ne prétend à aucune autorité
juridictionnelle.""",
    },
}

CONTENT["marketplace-seller-policy"] = {
    "en": {
        "title": "Marketplace & Seller Policy",
        "body": f"""## 1. Purpose

This policy defines how selling and buying works on the STAR
marketplace, operated by {OPERATOR}. It completes – without
overriding – the Terms of Service.

## 2. Becoming a seller

A seller is a supplier account that (a) registered a supplier profile
and (b) was verified by a platform administrator, and (c) maintains an
active paid seller subscription. Verified suppliers who let their
subscription lapse are automatically hidden from public buyers, cannot
publish new equipment and cannot restart shipping duty until
re-subscribed.

## 3. Listing obligations

A listing must:

- describe real, unused or clearly labelled refurbished hardware, with
  measured, honest quantities and SKU references;
- respect the category scheme of the marketplace;
- use the currency displayed without conversion tricks;
- keep up-to-date photos whenever the equipment has changed;
- remain accurate while active — the seller may unpublish, correct
  prices and quantities, and report availability.

Star records one published listing revision for audit.

## 4. Order handling

When an equipment order scrolls in, the supplier must confirm or return
stock sufficiency within the delivery window they configure. Shipping
re-synchronisation uses the shipment tracking visible to both parties.
Delivered hardware becomes the trustful responsibility of the supplier
until buyer confirmation.

## 5. Refunds and disputes

Buyers can request a refund through the platform workflow: first a
refund request (with reason), then supplier decision, then – if needed –
an administrator review with case evidence. Suppliers who repeatedly
decline justified refunds may lose marketplace rights.

## 6. Inventory integrity

The stock engine reserves, releases and deducts units automatically.
Suppliers must not override the quantities to mask overselling.

## 7. Data and audit

Supplier verification notes, listing revision history, shipment events
and dispute records are retained; personal contact details limited
to the pieces required for fulfilment.""",
    },
    "fr": {
        "title": "Politique du marketplace et des vendeurs",
        "body": """## 1. Objet

Cette politique définit les règles de vente et d'achat sur le marché
STAR opéré par [[Opérateur — à compléter]]. Elle complète – sans les
remplacer – les CGU.

## 2. Devenir vendeur

Un vendeur est un compte fournisseur qui (a) a enregistré un profil
fournisseur, (b) a été vérifié par un administrateur de plateforme, et
(c) maintient un abonnement vendeur payé actif. Les fournisseurs
vérifiés dont l'abonnement expire sont automatiquement masqués pour les
acheteurs publics, ne peuvent plus publier d'équipement et ne
reprendre l'activité de vente qu'après re-souscription.

## 3. Obligations d'annonces

Chaque annonce doit :

- décrire du matériel réel, neuf ou clairement identifié comme tel,
  avec des quantités et des références SKU honnêtes ;
- respecter le système de catégories du marketplace ;
- respecter la devise affichée sans conversion trompeuse ;
- tenir à jour les photos dès que le matériel change ;
- rester exact tant qu'elle est active — le vendeur peut dépublier,
  corriger prix et quantités, signaler la disponibilité.

Le service consigne une révision d'annonce publiée à des fins d'audit.

## 4. Gestion des commandes

Lorsqu'une commande arrive, le fournisseur confirme ou signale
l'indisponibilité dans son propre délai configuré. L'expédition est
suivie pour les deux parties via les informations de transport. Le
matériel livré reste sous la responsabilité du fournisseur jusqu'à
confirmation de l'acheteur.

## 5. Remboursements et litiges

L'acheteur peut demander un remboursement via le flux de la plateforme :
d'abord une demande motivée, puis la décision du fournisseur, puis — si
besoin — une revue par un administrateur avec les pièces versées. Un
vendeur qui refuse répétitivement des remboursements justifiés peut
perdre ses droits de vente.

## 6. Intégrité des stocks

Le moteur de stock réserve, restitue et soustrait automatiquement les
unités. Le fournisseur ne doit pas manipuler les quantités pour masquer
des ventes déjà promises.

## 7. Données et audit

Notes de vérification fournisseurs, historique des révisions d'annonce,
événements de transport et dossiers de litige sont conservés ;
seules les informations personnelles requises pour l'exécution sont
traitées.""",
    },
}

CONTENT["subscription-payment-refund-policy"] = {
    "en": {
        "title": "Subscription, Payment & Refund Policy",
        "body": f"""## 1. Purpose

This policy specifies the pricing, payment, renewal and refund rules
for STAR's paid seller subscriptions, from {OPERATOR}.

## 2. Plans

Selling on the marketplace requires an active paid plan. Current plan
prices are displayed in the application and enforced by the server at
subscription time. The very first calendar month of a seller's very
first plan may be offered at a welcome price; renewal and longer
periods follow the standard price table.

## 3. Periods and renewal

Subscriptions run for whole calendar months (or six months / twelve
months for longer plans) with a day clamp for shorter months. There is
**no automatic renewal**: a subscription only extends when the seller
explicitly pays again. Nothing can silently charge a card.

## 4. What happens when a payment fails

A failed, cancelled, or merely pending payment never grants selling
rights. The server confirms the outcome from its own signed provider
record before access resumes, so pending situations cannot invoke
privileges. Where the seller keeps an active subscription but misses
renewal, listing access pauses automatically on the expiry date.

## 5. Refund eligibility

Buyer payments (marketplace orders) follow the marketplace seller
policy. Seller subscription fees follow these rules:

- Non-activated subscriptions (server truncated solution, provider
  failure, billing errors) refunded in full within the demonstrated
  window.
- Subscriptions cancelled within the first cooling period (number
  equivalent in days to be fixed by the operator) may be refunded
  pro rata per full unused months at the operator's discretion.
- Active subscription periods already enjoyed – including the effect
  of a partial renewal window that was consumed in full – are not
  refunded on the seller's own initiative, except where required by
  law or by a goodwill exception recorded by a platform administrator.

## 6. Records

Every subscription start, outcome, activation, failure, expiry, refund
decision and payment rejection leaves a signed audit record, and the
subscription's history endpoint reproduces it for the seller.""",
    },
    "fr": {
        "title": "Politique d'abonnement, de paiement et de remboursement",
        "body": """## 1. Objet

Cette politique précise tarifs, paiements, renouvellement et
remboursements des abonnements payés du marché STAR, dont l'opérateur
est [[Opérateur — à compléter]].

## 2. Offres

Utiliser le marché en tant que vendeur requiert un plan actif payé. Les
tarifs affichés dans l'application sont appliqués par le serveur au
moment de la souscription. Le tout premier mois calendaire d'un premier
abonnement peut faire l'objet d'un tarif de bienvenue ; les
renouvellements et les périodes longues suivent la grille standard.

## 3. Périodes et renouvellement

L'abonnement court sur des mois calendaires entiers (ou six mois /
douze mois pour les formules longues), avec ajustement du jour pour les
mois courts. Il n'y a **aucun renouvellement automatique** : un
abonnement ne s'étend que si le vendeur paie une nouvelle fois. Rien ne
peut débiter une carte à l'insu de l'utilisateur.

## 4. Échec de paiement

Un paiement échoué, annulé ou seulement en attente n'accorde jamais de
droit de vente. Le serveur confirme l'issue depuis son enregistrement
fournisseur signé avant de rétablir l'accès ; un statut en attente ne
peut donc pas donner de privilège. Si l'abonnement expire, l'accès de
publication est suspendu automatiquement à la date d'expiration.

## 5. Éligibilité au remboursement

Les paiements acheteur (commandes du marché) suivent la politique du
marketplace. Les frais d'abonnement vendeur suivent ces règles :

- Abonnement jamais activé (défaillance fournisseur, facturation
  erronée) : remboursement intégral dans le délai démontré.
- Abonnement annulé pendant le délai « de réflexion » (durée
  [[définie par l'opérateur]]) : remboursement au prorata des mois
  entiers inutilisés, à la discrétion de l'opérateur.
- Les périodes consommées — y compris un renouvellement partiel
  entièrement joui — ne sont pas remboursées sur simple demande,
  sauf obligation légale ou geste commercial consigné par un
  administrateur.

## 6. Traces

Chaque démarrage d'abonnement, issue, activation, échec, expiration,
remboursement ou rejet laisse une trace d'audit signée que le vendeur
retrouve dans l'historique des abonnements.""",
    },
}

CONTENT["clinical-data-policy"] = {
    "en": {
        "title": "Clinical Data & Professional Responsibility Policy",
        "body": f"""## 1. Purpose

This policy explains how STAR handles surgical logbooks, procedure
records, attachments and competency assessments, from a
responsibility perspective. Operator: {OPERATOR}.

## 2. What STAR is, and is not

STAR is documentation and training software. It never produces
diagnosis, treatment recommendation or medical advice. Reviewed
records, grades and comments are informational artefacts of a
professional training process, not a certification, not a legal
medical record file.

## 3. Authorship and review

- A logbook procedure is always attributed to exactly one author
  (the operating professional) plus declared participants.
- Reviewing examiners approve, return or annotate via their own
  named account; review decisions are attributed and timestamped via
  the audit trail.
- Institution administrators manage rosters, placements and rubrics,
  but cannot edit the clinical content authored by other staff.

## 4. Patient data discipline

Every procedure references patients through pseudonymised references
(auto-generated identifiers). Free-text fields must not contain
patient names, ages with dates of birth or identity documents.
STAR reserves the right to scan attachments metadata and flag visible
PII, with the operator running the moderation workflow.

## 5. Institutional visibility

Records visibility follows the configured institution relation:
the author, their reviewing examiners, and their institution's
administrators see relevant records in the training flow. Records
placed under review can be locked against content drift until the
decision.

## 6. Assessments

Grades and exams follow the framework's rubric versions, never
overwritten: each assessment update keeps its event history. Released
grades are reserved to the configured degree of institution privacy,
and examiners hold a separate review role.

## 7. What counts as professional evidence

An approved record with examiner signature may be used as evidence of
practised procedures. STAR cannot assert the accuracy of declared
procedures beyond the platform's audit integrity (persistent records,
<i>no silent edits</i> of approved work).""",
    },
    "fr": {
        "title": "Politique des données cliniques et de la responsabilité professionnelle",
        "body": """## 1. Objet

Cette politique explique comment STAR traite carnets opératoires, fiches
d'intervention, pièces jointes et évaluations de compétences sous
l'angle des responsabilités. Opérateur : [[Opérateur — à compléter]].

## 2. Ce que STAR est — et n'est pas

STAR est un logiciel de documentation et de formation. Il ne produit
ni diagnostic, ni recommandation thérapeutique, ni conseil médical.
Les fiches relues, notes et commentaires sont des artefacts
informatifs d'un processus de formation, pas un certificat ni un
dossier médical de référence.

## 3. Auteurs et relecture

- Chaque intervention est rattachée à exactement un auteur (le
  professionnel opérateur) plus les participants déclarés.
- Les examinateurs valident, retournent ou annotent via leur propre
  compte nominatif ; leurs décisions sont attribuées et horodatées
  dans la piste d'audit.
- Les administrateurs gèrent affectations, placements et grilles mais
  ne modifient pas le contenu clinique d'autres personnes.

## 4. Discipline des données patients

Toute intervention référence des patients par identifiants
pseudonymisés. Les champs libres ne doivent pas contenir de nom de
patient, de naissance complète ou de pièce d'identité. STAR se réserve
d'analyser les métadonnées des pièces jointes et de signaler les
données visibles, la modération restant de la responsabilité de l'opérateur.

## 5. Visibilité institutionnelle

La visibilité suit le rattachement d'établissement : l'auteur, ses
examinateurs relais et les administrateurs de son établissement voient
les fiches pertinentes dans le parcours de formation. Les fiches en
relecture peuvent être verrouillées jusqu'à décision.

## 6. Évaluations

Les notes suivent les versions de grilles du référentiel, jamais
écrasées : chaque mise à jour conserve son historique. Les notes
publiées respectent le niveau de confidentialité configuré, et les
examinateurs disposent d'un rôle de relecture distinct.

## 7. Force probante

Une fiche approuvée avec signature d'examinateur peut servir à attester
une pratique déclarée. STAR ne peut garantir l'exactitude des
interventions déclarées au-delà de l'intégrité d'audit de la
plateforme (enregistrements persistants, pas d'édition silencieuse du
travail approuvé).""",
    },
}

CONTENT["cookies-data-retention-policy"] = {
    "en": {
        "title": "Cookies & Data Retention Policy",
        "body": f"""## 1. Purpose

This policy lists the cookies and browser storage STAR uses and how
long different classes of data are kept. Operator: {OPERATOR}.

## 2. Cookies and local storage

STAR uses only functional browser storage:

- **Session tokens** – secure, HTTP-only cookies or storage entries
  needed to keep a signed-in user logged in; they expire on logout or
  by server policy.
- **Language preference** – to keep the interface language across
  visits.
- **Server URL (mobile)** – the mobile app stores the address of the
  STAR instance it connects to.
- **Onboarding visited flags** – whether the guided tour has been
  seen; deletable at any time.

STAR does not run advertising cookies, social-media trackers or
third-party analytics scripts that would profile users across sites.

## 3. Retention of account data

Profiles and role assignments are retained while needed for the
service. Deleting an account removes or anonymises the mostly
personal parts and keeps statutory bookkeeping records (invoices,
audit trail entries about financial events) for the retention period
fixed by the operator.

## 4. Retention of technical logs

Audit trail entries are retained in a tamper-evident way. Access
records, including IP addresses and user agents, are kept for
security purposes and rotated by the operator's backup schedule,
then destroyed.

## 5. How to exercise rights

Any person can exercise their data rights via the Privacy Request
workflow or {CONTACT}. Users may delete their own account and see
their consent history from the Settings → Privacy area.""",
    },
    "fr": {
        "title": "Politique de cookies et de conservation des données",
        "body": """## 1. Objet

Cette politique recense les cookies et stockages navigateurs utilisés
par STAR et la durée de conservation des différentes classes de
données. Opérateur : [[Opérateur — à compléter]].

## 2. Cookies et stockage local

STAR n'utilise que le stockage fonctionnel :

- **Jetons de session** – cookies sécurisés, HTTP-only, nécessaires
  pour maintenir la session ; ils expirent à la déconnexion ou selon
  la politique du serveur.
- **Langue préférée** – pour conserver la langue de l'interface.
- **URL du serveur (mobile)** – l'application mobile mémorise
  l'adresse de l'instance STAR à laquelle elle se connecte.
- **Indicateurs de visite (parcours initial)** – si la visite guidée a
  été vue ; supprimables à tout moment.

STAR n'embarque ni cookies publicitaires, ni traceurs réseaux sociaux,
ni scripts d'analyse tiers qui profileraient les utilisateurs.

## 3. Conservation des données de compte

Les profils et rôles sont conservés tant que nécessaire au service.
La suppression d'un compte efface ou anonymise les données essentiellement
personnelles, tout en conservant les écritures comptables (factures,
piste d'audit des évènements financiers) pour la durée fixée par
l'opérateur.

## 4. Conservation des journaux techniques

Les entrées de la piste d'audit sont conservées de manière
infalsifiable. Les enregistrements d'accès (adresses IP, agents
utilisateurs) sont conservés à des fins de sécurité puis détruits
selon le calendrier de sauvegarde de l'opérateur.

## 5. Exercer vos droits

Toute personne peut exercer ses droits via le flux de Demandes de
confidentialité ou [[e-mail de contact — à compléter]]. Les
utilisateurs peuvent aussi supprimer leur propre compte et consulter
leur historique de consentements (Réglages → Confidentialité).""",
    },
}

POLICY_META: dict[str, dict] = {
    "privacy-policy": {"title": "Privacy Policy", "category": "privacy"},
    "terms-of-service": {"title": "Terms of Service", "category": "terms"},
    "marketplace-seller-policy": {
        "title": "Marketplace & Seller Policy",
        "category": "marketplace",
    },
    "subscription-payment-refund-policy": {
        "title": "Subscription, Payment & Refund Policy",
        "category": "payments",
    },
    "clinical-data-policy": {
        "title": "Clinical Data & Professional Responsibility Policy",
        "category": "clinical",
    },
    "cookies-data-retention-policy": {
        "title": "Cookies & Data Retention Policy",
        "category": "data_retention",
    },
}

RELATED: list[tuple[str, str]] = [
    ("terms-of-service", "privacy-policy"),
    ("terms-of-service", "marketplace-seller-policy"),
    ("marketplace-seller-policy", "subscription-payment-refund-policy"),
    ("privacy-policy", "clinical-data-policy"),
    ("privacy-policy", "cookies-data-retention-policy"),
]

VERSION = "1.0"


class Command(BaseCommand):
    help = (
        "Seed the Policies & Legal Center: six bilingual policies as version 1.0 "
        "drafts. Nothing is published — a platform administrator must review and "
        "publish each text through /admin/legal. Idempotent: existing v1.0 texts "
        "are left untouched."
    )

    def handle(self, *args, **options):
        policy_map: dict[str, Policy] = {}
        for slug, meta in POLICY_META.items():
            policy, policy_created = Policy.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": meta["title"],
                    "category": meta["category"],
                    "summary": CONTENT[slug]["en"]["body"][:240].replace("\n", " "),
                },
            )

            policy_map[slug] = policy

        for left, right in RELATED:
            policy_map[left].related_policies.add(policy_map[right])
            policy_map[right].related_policies.add(policy_map[left])

        draft_count = 0
        for slug, languages in CONTENT.items():
            policy = policy_map[slug]
            for language in ("en", "fr"):
                text = languages[language]
                if PolicyVersion.objects.filter(
                    policy=policy, language=language, version=VERSION
                ).exists():
                    continue
                source = PolicyVersion.objects.filter(
                    policy=policy, language="en", version=VERSION
                ).first()
                PolicyVersion.objects.create(
                    policy=policy,
                    translation_of=source if language == "fr" else None,
                    language=language,
                    version=VERSION,
                    title=text["title"],
                    body=text["body"],
                    # Drafts only: publication is a reviewed administrator
                    # action, never a side effect of seeding.
                    status=PolicyVersion.Status.DRAFT,
                )
                draft_count += 1

        self.stdout.write(
            f"Legal center seeded: {len(POLICY_META)} policies, "
            f"{draft_count} new bilingual drafts (nothing published)."
        )
