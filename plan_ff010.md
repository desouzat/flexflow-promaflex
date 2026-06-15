# FF-HARDENING-010 — Implementation Plan

## Task 1: Tooltip Update
- File: KanbanPage.jsx
- Find: "Modo de Falha" / "slaJustification" tooltip ?
- Replace text

## Task 2: Financeiro Layout Cleanup
- 2a: Remove NF-e / GCS link duplicates in Financeiro accordion
- 2b: Commission section gated on admin/master role
- 2c: Remove empty "Concluídos" accordion for archived POs

## Task 3: SLA Justification Read-only outside PCP
- Add disabled={selectedPO?.status !== 'PCP' && !['admin','master','pcp'].includes(user?.role?.toLowerCase())}

## Task 4: SLA Settings Page
- Backend: GET/PUT /settings/sla-config
- GlobalConfig model fields: sla_total_hours, sla_area_hours, sla_start_hour, sla_end_hour, sla_working_days
- Frontend: SettingsPage.jsx - new SLA config panel

## Task 5: Business Hours Calculation
- Python helper: calculate_business_hours(start_time, end_time, config)
- Inject into PO serialization in kanban.py
- Frontend: display X.Xh / Nh

## Notes to verify from research:
- GlobalConfig model exists?
- Existing settings router?
- Kanban board endpoint PO serialization format
- SLA fields already in the board response
