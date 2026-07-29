# Public data source inventory

This inventory records public aggregate files obtained for review before Prompt 11. The source
workbooks remain under ignored `data/external/` paths and are not committed. Their original
worksheets and columns have not been modified.

## Michigan Department of Education

- **Dataset:** Bulletin 1014, 2024-25 district financial and pupil information export
- **Publisher:** Michigan Department of Education
- **Landing page:** <https://www.michigan.gov/mde/services/financial-management/state-aid/publications/bulletin-1014-michigan-public-schools-ranked-by-select-financial-information>
- **Downloaded file:** `data/external/mi_school_data/25_Bulletin1014Export.xlsx`
- **Direct source:** <https://mdoe.state.mi.us/SAMSPublic/Reports/others/25_Bulletin1014Export.xlsx>
- **Retrieved:** 2026-07-29
- **Size:** 482,366 bytes
- **SHA-256:** `0e1634f8861d1c25595079ba69e9dc7a842a3386c5bc98aefd6538df629b9c09`
- **Classification:** Public aggregate district-level education data
- **Review status:** Licensing terms and repository file-size implications require review before
  the workbook may be committed or ingested.

## National Center for Education Statistics

- **Dataset:** Table 1, operational and student membership status of public elementary and
  secondary schools and agencies, school year 2023-24
- **Publisher:** National Center for Education Statistics, Common Core of Data
- **Landing page:** <https://nces.ed.gov/ccd/tables/202324_summary_1.asp>
- **Downloaded file:** `data/external/nces/202324_summary_1.xlsx`
- **Direct source:** <https://nces.ed.gov/ccd/tables/xls/202324_summary_1.xlsx>
- **Retrieved:** 2026-07-29
- **Size:** 14,728 bytes
- **SHA-256:** `e0edb8b2f9b9e5e0746d0880dfaf838917f50b639195f1225f8ade439aa7a676`
- **Classification:** Public aggregate national education data
- **Review status:** Licensing terms and repository file-size implications require review before
  the workbook may be committed or ingested.

## Integrity checks

Both downloads identify as Microsoft Excel 2007+ workbooks and pass ZIP archive integrity checks.
No workbook content, worksheet names, headers, or columns were changed after download.
