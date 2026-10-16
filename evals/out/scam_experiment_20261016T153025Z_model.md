# Scam experiment 20261016T153025Z

**30/30 caught, 0/20 false alarms** (mode `model`, model `anthropic.claude-haiku-4-5`, cases n_base 50 + n_village 0 = 50)

- exact decision match: 49/50; benign blocked outright: 0/20; errors: 0; extraction errors: 0
- extraction p50 1205.8 ms, p95 1407.0 ms; gate max 1.377 ms; wall 59.29 s
- caught = scam case whose mapped decision is verify_with_member, advise_do_not_send or deny; false alarm = benign case mapped to advise_do_not_send/deny, or to verify_with_member when expected is record

| id | set | scam | expected | got | rule | claimed | extractor | pass | extract ms |
|---|---|---|---|---|---|---|---|---|---|
| se_s01 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1612.2 |
| se_s02 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1329.9 |
| se_s03 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1429.1 |
| se_s04 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1259.2 |
| se_s05 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1147.3 |
| se_s06 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1039.7 |
| se_s07 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1071.6 |
| se_s08 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1029.2 |
| se_s09 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1232.8 |
| se_s10 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1217.7 |
| se_s11 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1221.0 |
| se_s12 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1070.2 |
| se_s13 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1225.2 |
| se_s14 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1298.7 |
| se_s15 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1201.1 |
| se_s16 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1112.7 |
| se_s17 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1375.6 |
| se_s18 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1273.3 |
| se_s19 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1292.4 |
| se_s20 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_ana | model:anthropic.claude-haiku-4-5 | PASS | 1344.9 |
| se_s21 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_lucia | model:anthropic.claude-haiku-4-5 | PASS | 1324.1 |
| se_s22 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1247.2 |
| se_s23 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1079.6 |
| se_s24 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 922.1 |
| se_s25 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1368.8 |
| se_s26 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1036.7 |
| se_s27 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1407.0 |
| se_s28 | base | Y | advise_do_not_send | advise_do_not_send | R-MONEY-UNKNOWN | - | model:anthropic.claude-haiku-4-5 | PASS | 1223.6 |
| se_s29 | base | Y | deny | deny | R-MONEY-NEVER | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1269.3 |
| se_s30 | base | Y | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1065.8 |
| se_b01 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1208.3 |
| se_b02 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1167.0 |
| se_b03 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1275.2 |
| se_b04 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1350.6 |
| se_b05 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1091.8 |
| se_b06 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1363.2 |
| se_b07 | base | N | verify_with_member | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1205.8 |
| se_b08 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1056.9 |
| se_b09 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1388.6 |
| se_b10 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 853.4 |
| se_b11 | base | N | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_marco | model:anthropic.claude-haiku-4-5 | PASS | 1085.5 |
| se_b12 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 972.8 |
| se_b13 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 949.9 |
| se_b14 | base | N | verify_with_member | verify_with_member | R-MONEY-VERIFY | m_ana | model:anthropic.claude-haiku-4-5 | PASS | 1091.5 |
| se_b15 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 992.0 |
| se_b16 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 922.2 |
| se_b17 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1172.9 |
| se_b18 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1083.7 |
| se_b19 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1126.9 |
| se_b20 | base | N | record | record | no_tool_call | - | model:anthropic.claude-haiku-4-5 | PASS | 1185.9 |
