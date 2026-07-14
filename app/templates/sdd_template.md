# Solution Design Document

## Informasi Dokumen

| Field | Isi |
| --- | --- |
| Nama Project | {{ project_name }} |
| No. Solution Design | *(diisi manual)* |
| RFC # | *(diisi manual)* |
| Versi | *(diisi manual)* |
| Document Classification | *(diisi manual)* |

## Document Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
| --- | --- | --- | --- | --- |
| | | | | |

## Application Revision History

| No. | Version | Revision Date | Changed By | Summary of Changes |
| --- | --- | --- | --- | --- |
| | | | | |

## Persetujuan Dokumen

*(diisi manual — timeline aktivitas, cost estimation, dan tanda tangan perwakilan user & pengembang)*

## 1. Deskripsi Aplikasi

{{ app_description }}

## 2. Application Dev System Type

*(diisi manual — ERP / NON ERP)*

## 3. Informasi Demografi Aplikasi

| No. | Subject | Uraian | Remark |
| --- | --- | --- | --- |
| 1 | Business Requestor | *(diisi manual)* | |
| 2 | Business User | *(diisi manual)* | |
| 3 | Projected User Number | *(diisi manual)* | |
| 4 | Value (Rp) | *(diisi manual)* | |
| 5 | Application Coverage Area | *(diisi manual)* | |
| 6 | Collaboration Profile | *(diisi manual)* | |
| 7 | Technology Capability | *(diisi manual)* | |

## 4. System Requirement

{% for requirement in system_requirements %}
- {{ requirement }}
{% endfor %}

## 5. How to Access

*(diisi manual)*

## 6. Infrastructure & Capacity Planning

*(diisi manual)*

## 7. Application Architecture

### 7.1 System Architecture

![System Architecture Diagram]({{ diagrams.system_architecture_image }})

### 7.2 Component Integration

![Component Integration Diagram]({{ diagrams.component_integration_image }})

## 8. Application Security

| No. | Check List | Remark |
| --- | --- | --- |
| 1 | Penetration Test | *(diisi manual)* |
| 2 | Secure Coding Practice | *(diisi manual)* |
| 3 | Reverse Proxy | *(diisi manual)* |

## 9. Application Features Requirement

*(diisi manual — daftar fitur aplikasi beserta deskripsinya)*

## 10. Flow Proses Bisnis

{{ business_flow_description }}

## 11. Use Case

![Use Case Diagram]({{ diagrams.use_case_diagram_image }})

*(diisi manual — tabel detail use case per aktor: Pre-Condition, Description, Acceptance Criteria)*

## 12. Activity Diagram

{% for activity in diagrams.activity_diagrams %}
### 12.{{ loop.index }} {{ activity.activity_name }}

{{ activity.description }}

![{{ activity.activity_name }}]({{ activity.image_path }})

{% endfor %}
