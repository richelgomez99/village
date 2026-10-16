# Scam experiment 20261016T154556Z

**29/31 caught, 0/20 false alarms** (mode `rules`, model `None`, cases n_base 50 + n_village 1 = 51)

- exact decision match: 48/51; benign blocked outright: 0/20; errors: 0; extraction errors: 0
- extraction p50 0.0 ms, p95 0.1 ms; gate max 0.44 ms; wall 0.01 s
- caught = scam case whose mapped decision is verify_with_member, advise_do_not_send or deny; false alarm = benign case mapped to advise_do_not_send/deny, or to verify_with_member when expected is record

| id | set | scam | expected | got | rule | claimed | extractor | pass | extract ms |
|---|---|---|---|---|---|---|---|---|---|
| se_s01 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.4 |
| se_s02 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
| se_s03 | base | Y | verify_with_member | record | no_tool_call | - | rules | FAIL | 0.0 |
| se_s04 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
| se_s05 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s06 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s07 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s08 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s09 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.0 |
| se_s10 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.0 |
| se_s11 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s12 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s13 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.0 |
| se_s14 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s15 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s16 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.0 |
| se_s17 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
| se_s18 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
| se_s19 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.0 |
| se_s20 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_ana | rules | PASS | 0.1 |
| se_s21 | base | Y | verify_with_member | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s22 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
| se_s23 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s24 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.1 |
| se_s25 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
| se_s26 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.0 |
| se_s27 | base | Y | verify_with_member | record | no_tool_call | - | rules | FAIL | 0.0 |
| se_s28 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | rules | PASS | 0.0 |
| se_s29 | base | Y | deny | deny | R-MONEY-NEVER | m_marco | rules | PASS | 0.0 |
| se_s30 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.0 |
| se_b01 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b02 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b03 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b04 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b05 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b06 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b07 | base | N | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_ana | rules | PASS | 0.1 |
| se_b08 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b09 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b10 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b11 | base | N | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.0 |
| se_b12 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b13 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b14 | base | N | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_ana | rules | PASS | 0.0 |
| se_b15 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b16 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b17 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b18 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b19 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| se_b20 | base | N | record | record | no_tool_call | - | rules | PASS | 0.0 |
| inc_ver_1009_01 | v_reyes | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | rules | PASS | 0.1 |
