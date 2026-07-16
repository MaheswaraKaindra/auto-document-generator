## Informasi Dokumen

| Field | Isi |
| --- | --- |
| Nama Project | {{ project_name }} |
| Related RFC # | {{ meta.related_rfc_number }} |
| Related Work Order # | {{ meta.related_work_order }} |
| Change Owner | {{ meta.change_owner }} |
| Prepared By | {{ meta.prepared_by }} |
| Preparation Date | {{ meta.preparation_date }} |
| Reviewed By | {{ meta.reviewed_by }} |
| Review Date | {{ meta.review_date }} |

## Distribution List

{{ meta.distribution_list }}

## Version History

| Ver. No. | Ver. Date | Revised By | Description | File Name |
| --- | --- | --- | --- | --- |
| | | | | |

## Rencana Penerimaan User Acceptance Test ("UAT")

Dokumen ini menjelaskan prosedur pelaksanaan pengujian fungsional serta metode pengujian yang digunakan dalam rangka {{ project_name }}.

Persetujuan atas dokumen ini oleh perwakilan pengguna pengujian menunjukkan bahwa hasil pengujian telah sesuai dengan kebutuhan, dan dengan demikian pengujian dianggap diterima.

Nama, jabatan, dan tanda tangan perwakilan user pengujian serta perwakilan pengembang dibubuhkan pada dokumen cetak saat persetujuan diberikan.

## Sertifikasi Keberhasilan Pelaksanaan Pengujian

Tanggal penyelesaian, klasifikasi hasil (Lolos/Gagal), dan tanda tangan diisi setelah seluruh kasus pengujian pada Bab 3 selesai dieksekusi. Bagian ini sengaja dikosongkan — hasilnya belum ada saat dokumen ini dibuat.

## 1. Prosedur Pengujian

### 1.1 Entry Criteria

Eksekusi pengujian hanya akan dilakukan jika kriteria-kriteria berikut sudah terpenuhi:

1. Implementasi pembuatan tampilan dan fitur {{ project_name }} telah tersaji secara penuh pada environment QAS dan dapat berfungsi dengan semestinya.

### 1.2 Exit Criteria

UAT hanya akan dianggap berhasil jika semua permasalahan yang timbul selama pelaksanaan pengujian telah diselesaikan dan ketika semua kasus pengujian, seperti yang dinyatakan dalam rencana pengujian yang telah disetujui, telah mendapat hasil yang diinginkan.

### 1.3 Formulir dan Dokumentasi

Setiap kasus pengujian yang diselesaikan oleh penguji akan didokumentasikan dengan salah satu dari status berikut.

| Status | Deskripsi |
| --- | --- |
| Lolos | Diterima apa adanya |
| Gagal | Tidak diterima dengan klarifikasi |

Semua kasus pengujian yang berstatus Gagal lebih lanjut harus dijelaskan dalam kolom Komentar, dan harus diberi kode kegagalan sebagai berikut:

| Kode Kegagalan | Deskripsi |
| --- | --- |
| A | Kecacatan besar atau kesalahan desain, kesalahan pada operasi software atau hardware. |
| B | Kelanjutan dari pengujian kasus tidak dapat dilakukan lagi. |
| C | Pengujian dapat terus dilakukan namun dengan beberapa keterbatasan. |
| D | Kesalahan yang menyebabkan ketidaknyamanan penggunaan oleh user tapi tidak berpengaruh langsung terhadap fungsi sistem. |

Pada saat eksekusi semua kasus pengujian telah diselesaikan, Sertifikasi Keberhasilan Pelaksanaan Pengujian harus diisi dan ditandatangani.

## 2. Ringkasan Aplikasi

{{ app_description }}

## 3. Case Pengujian

Kolom **Penguji**, **Tanggal Pengujian**, **Status**, dan **Komentar** diisi manual oleh tim penguji setelah pengujian benar-benar dilaksanakan — kolom ini tidak bisa dihasilkan otomatis dari kode.

| No | Role | Kegiatan | Langkah-Langkah Pengujian | Hasil yang Diharapkan | Penguji | Tanggal Pengujian | Status | Komentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{% for tc in uat_test_cases -%}
| {{ tc.test_id }} | {{ tc.role }} | {{ tc.activity }} | {{ tc.steps }} | {{ tc.expected_result }} | | | | |
{% endfor %}
