# NOTICE — anonymization & reference-copy disclosure

> Copyright and license (Apache-2.0 from 0.2.0; MIT up to v0.1.2): see [`NOTICE`](./NOTICE) and [`LICENSE`](./LICENSE).

이 하네스는 실제 SI 프로젝트에서 운영하던 것을 **익명화해 공개**한 것입니다.
This harness was distilled from a real SI (system-integration) project and **anonymized before release**.

## What was changed / 바뀐 것

All project-specific identifiers were replaced with generic placeholders. The same real value maps to
the same placeholder everywhere:

| Type | Replaced with |
|---|---|
| Schemas / tables | `sch_a`–`sch_d`, `tbl_001`… |
| Common-code values | `CD001`… |
| Screen / program / process IDs | `screen-001`, `UI-X001`, `PG-XX0001`… |
| Service names | `admin-portal`, `buyer-portal`, `supplier-portal`, `contract-service`, `catalog-service`, `member-service`, `settlement-service`, `integration-hub` |
| Business URLs | `/portal/path-001`… |
| Internal IPs / DB names / network | `<내부 IP>`, `<개발 DB 이름>`, `<내부 네트워크>` |
| Project / team prefixes | `PRJ`, `prj_*`, `team2` |
| Home directory | `{본인 경로}` (placeholder for your `~` / `C:\Users\<you>`) |
| Other people's names / accounts | `작업자A`, `accountA`… |

## What was intentionally kept / 의도적으로 유지한 것

- **Public-procurement business terms** (수요기관, 공급업체, 납품요청, 검수, 견적요청, 인지세 …) — they convey
  the methodology and carry no secret.
- **The author's own identifiers**: `백가희`, `ghbaek`, `neisii`.
- **Harness design terms** (role sessions such as `qa-master`, rule IDs such as `GL-01`, `AG-15`) — these are
  the harness itself, not client data.

## Important / 유의

- **The bundled scripts are reference copies.** Paths (`{본인 경로}`), service names, and table names were
  genericized, so they will **not run as-is** in your environment — adapt the values first. Scripts shipped as
  installable skills (see `skills/`) were rewritten to be portable and use only the standard library.
- **No secrets** (DB accounts, tokens, passwords) are included anywhere in this repository.
- The original harness ran on **Windows**; Windows-only tooling (PowerShell scripts, unsigned `.exe`/C# widgets)
  was **excluded** from this public release and is only described, not shipped.
- The rule documents under `rules/` are the **canonical source (정본)** and are kept in Korean.
- **Skill scripts have no shebang line.** Run them with Python as each `SKILL.md` shows
  (`python -X utf8 <script>`); they are not meant to be executed directly (`./script.py`).
- **Dogfood records in `design-notes/` (0.2.0)** come from the author's own sample repository, not from the
  client project. They contain no client data. / `design-notes/`의 개밥(dogfooding) 기록은 원 프로젝트가 아니라
  작성자가 만든 시험용 저장소에서 나온 것이며, 고객 데이터를 담고 있지 않습니다.

If you believe any residual identifier slipped through, please open an issue.
