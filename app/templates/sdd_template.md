# Solution Design Document

## Informasi Dokumen

| Field | Isi |
| --- | --- |
| Nama Project | {{ project_name }} |
| No. Solution Design | {{ meta.solution_design_no }} |
| RFC # | {{ meta.rfc_number }} |
| Versi | {{ meta.version }} |
| Document Classification | {{ meta.document_classification }} |

## Document Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
| --- | --- | --- | --- | --- |
| | | | | |

## Application Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
| --- | --- | --- | --- | --- |
| | | | | |

## Persetujuan Dokumen

Timeline aktivitas, cost estimation, serta tanda tangan perwakilan user dan pengembang dilengkapi pada dokumen cetak setelah dokumen ini disetujui. Bagian ini memang dikosongkan — tanda tangan tidak dapat dihasilkan oleh sistem.

## 1. Deskripsi Aplikasi

{{ app_description }}

## 2. Application Dev System Type

{{ meta.dev_system_type }}

## 3. Informasi Demografi Aplikasi

| No. | Subject | Uraian | Remark |
| --- | --- | --- | --- |
| 1 | Business Requestor | {{ meta.business_requestor }} | |
| 2 | Business User | {{ meta.business_user }} | |
| 3 | Projected User Number | {{ meta.projected_user_number }} | |
| 4 | Value (Rp) | {{ meta.value_rp }} | |
| 5 | Application Coverage Area | {{ meta.coverage_area }} | |
| 6 | Collaboration Profile | {{ meta.collaboration_profile }} | |
| 7 | Technology Capability | {{ meta.technology_capability }} | |

## 4. System Requirement

{% for requirement in system_requirements %}
- {{ requirement }}
{% endfor %}

## 5. How to Access

{{ meta.how_to_access }}

## 6. Infrastructure & Capacity Planning

{{ meta.infrastructure_capacity }}

## 7. Application Architecture

### 7.1 System Architecture

![System Architecture Diagram]({{ diagrams.system_architecture_image }})

### 7.2 Component Integration

![Component Integration Diagram]({{ diagrams.component_integration_image }})

## 8. Application Security

| No. | Check List | Remark |
| --- | --- | --- |
| 1 | Penetration Test | {{ meta.security_penetration_test }} |
| 2 | Secure Coding Practice | {{ meta.security_secure_coding }} |
| 3 | Reverse Proxy | {{ meta.security_reverse_proxy }} |

## 9. Application Features Requirement

| No. | Fitur Aplikasi | Deskripsi Fitur |
| --- | --- | --- |
{% for feature in feature_requirements -%}
| {{ loop.index }} | {{ feature.feature_name }} | {{ feature.description }} |
{% endfor %}

## 10. Flow Proses Bisnis

{{ business_flow_description }}

## 11. Use Case

![Use Case Diagram]({{ diagrams.use_case_diagram_image }})

{% for uc in use_cases %}
### 11.{{ loop.index }} Use Case {{ uc.use_case_id }} — {{ uc.actor }}

| Field | Isi |
| --- | --- |
| No. Use Case | {{ uc.use_case_id }} |
| Actor | {{ uc.actor }} |
| Pre-Condition | {{ uc.pre_condition }} |
| Description | {{ uc.description }} |

Acceptance Criteria:
{% for criterion in uc.acceptance_criteria %}
{{ loop.index }}. {{ criterion }}
{% endfor %}
{% endfor %}

## 12. Activity Diagram

{% for activity in diagrams.activity_diagrams %}
### 12.{{ loop.index }} {{ activity.activity_name }}

{{ activity.description }}

![{{ activity.activity_name }}]({{ activity.image_path }})

{% endfor %}
