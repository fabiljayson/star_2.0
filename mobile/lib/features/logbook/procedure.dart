/// Domain models for the surgical logbook.
/// Mirrors web/src/lib/types.ts `SurgicalProcedure`.
class ProcedureParticipant {
  ProcedureParticipant({
    required this.user,
    required this.userDetail,
    required this.role,
  });

  final String user;
  final SummaryUser userDetail;
  final String role;

  factory ProcedureParticipant.fromJson(Map<String, dynamic> json) =>
      ProcedureParticipant(
        user: '${json['user']}',
        userDetail: SummaryUser.fromJson(
          (json['user_detail'] ?? const {}) as Map<String, dynamic>,
        ),
        role: '${json['role']}',
      );

  Map<String, dynamic> toJson() => {'user': user, 'role': role};
}

class SummaryUser {
  SummaryUser({
    required this.id,
    required this.email,
    required this.fullName,
  });

  final String id;
  final String email;
  final String fullName;

  factory SummaryUser.fromJson(Map<String, dynamic> json) => SummaryUser(
        id: '${json['id']}',
        email: (json['email'] ?? '') as String,
        fullName: (json['full_name'] ?? '').toString(),
      );
}

class Procedure {
  Procedure({
    required this.id,
    required this.reference,
    required this.status,
    required this.procedureDate,
    required this.category,
    required this.procedureName,
    required this.indication,
    required this.summary,
    required this.author,
    required this.version,
    this.patientReferenceCode,
    this.departmentName,
  });

  final String id;
  final String reference;
  final String status;
  final String procedureDate;
  final String category;
  final String procedureName;
  final String indication;
  final String summary;
  final SummaryUser? author;
  final int version;
  final String? patientReferenceCode;
  final String? departmentName;

  factory Procedure.fromJson(Map<String, dynamic> json) => Procedure(
        id: '${json['id']}',
        reference: '${json['reference'] ?? ''}',
        status: '${json['status'] ?? ''}',
        procedureDate: '${json['procedure_date'] ?? ''}',
        category: '${json['category'] ?? ''}',
        procedureName: '${json['procedure_name'] ?? ''}',
        indication: (json['indication'] ?? '').toString(),
        summary: (json['summary'] ?? '').toString(),
        author: json['author_detail'] == null
            ? null
            : SummaryUser.fromJson(json['author_detail'] as Map<String, dynamic>),
        version: (json['version'] ?? 0) as int,
        patientReferenceCode:
            json['patient_reference_code']?.toString(),
        departmentName: json['department_name']?.toString(),
      );
}

class ProcedureCreateInput {
  ProcedureCreateInput({
    required this.institutionId,
    required this.procedureDate,
    required this.category,
    required this.procedureName,
    required this.indication,
    required this.summary,
  });

  final String institutionId;
  final String procedureDate;
  final String category;
  final String procedureName;
  final String indication;
  final String summary;

  Map<String, dynamic> toJson() => {
        'institution': institutionId,
        'procedure_date': procedureDate,
        'category': category,
        'procedure_name': procedureName,
        'indication': indication,
        'summary': summary,
      };
}

/// Domain errors shared by screens.
class ProcedureSubmitException implements Exception {
  ProcedureSubmitException(this.message);
  final String message;
  @override
  String toString() => 'ProcedureSubmitException: $message';
}
