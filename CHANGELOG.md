# Changelog
## [Unreleased]

- raise coverage to 95%+ and enforce via AGENTS.md and pyproject.toml (6673c7c90d725cc0190cd03cafdd6edd27e4872d)

- fix ecosystem table names, badges, and Part of intro line (b030558fe0166ecc64bc3f439ade362fd74c7a65)

- mark cookbook as dogfood, fix ecosystem table description (2d367d0ea9fc0ff4de81b5b730af561976f2f00a)

- replace non-existent python-dx link with cookbook repo (fe4960bb3cb7eb22d013108bfdf463725fbe9433)

- fix cross-repo links and README title (fa2509179ebea3aa415f28ce172260a1f9dc9ba6)

- Add DX Toolkit hub link to README (073b16155d39da8e9b37fa4b08c17e8472b62fdb)

- update changelog (9f5ce2cda749c5808d5c55239eec22c50cf9b3c8)

- bump version to 0.17.0 (fd3389cc1eec3810cb952dd0354c22c4082244d2)

- bump expected version to 0.17.0 (0af4c34086b032177bac27370bc1d33eeef3ec2e)

- add Issue Conventions section to AGENTS.md (2dcf16a28192ce65fb63f808ddd28ad754b0bf43)

- warn on native-extension dependencies in requirements.txt (#150) (4a651c48c5bd46c5518b3121d9571ff302ea4f92)

- add --target-python to evaluate deployment runtime separately (#149) (c22df160356b5db17512361d1182ef8c22f2e725)

- warn on declared but unregistered Blueprints (#148) (c77cef27944e0e2c5889897de56c0c4234199337)

- classify non-v2 programming models as unsupported (#147) (949c4225f1b89e9d018a385aa26b5609eae7b5ea)

- Merge pull request #136 from yeongseon/dependabot/github_actions/actions/github-script-9.0.0

chore(deps): bump actions/github-script from 8.0.0 to 9.0.0 (eb04c418f15f56df9cd4b63a4db2ded2825caab3)

- Merge pull request #137 from yeongseon/dependabot/github_actions/actions/upload-artifact-7.0.1

chore(deps): bump actions/upload-artifact from 7.0.0 to 7.0.1 (43938a745b6773db92984fbcf1a7be64e51c3145)
## [0.16.3] - 2026-04-10

- update changelog (8766d76ff321c9eed851af79453c15404f829f69)

- bump version to 0.16.3 (f3b801852d3833a2d86ef5e1177231a4d12e362f)

- bump ruff from 0.15.9 to 0.15.10 (#135) (c882a09fab308a3dd156d88bbaa40de7fb7f1bf2)

- standardize ecosystem table in README (ec14e5e7406a786f0e2c63442398f43007803023)

- add llms.txt for LLM-friendly documentation (#130) (#131) (74fc2995857c501302e854af42241223ee58cdfc)

- resolve MkDocs strict-mode failures for nav and links (#128) (#129) (56f097b755a06944cce3a693bd64405380b87ec4)

- Merge pull request #108 from yeongseon/dependabot/github_actions/softprops/action-gh-release-2.6.1

chore(deps): bump softprops/action-gh-release from 2.2.2 to 2.6.1 (bce328bb361a4ca18d2c88154388df5a7d2bf71c)

- Merge pull request #109 from yeongseon/dependabot/pip/mypy-1.20.0

chore(deps): bump mypy from 1.19.1 to 1.20.0 (8e8727c5310ce81cd50e6245b9237d379ab00699)

- Merge pull request #110 from yeongseon/dependabot/pip/ruff-0.15.9

chore(deps): bump ruff from 0.15.8 to 0.15.9 (637732b0c789e2d148990c6e5e05f99dce332a42)

- Merge pull request #127 from yeongseon/docs/deployment-consistency-fix

docs: normalize storage naming rule formatting (b046e62f1606d790b3065558b816d6f375f0817d)

- normalize storage naming rule to use en-dash (3–24) (79f0c5b47e515504e995975e48264a66ede8a02c)

- Merge pull request #126 from yeongseon/docs/deployment-rewrite

docs: rewrite deployment guide for developer-friendly experience (adf6f313f58b336493abf78b3eacb7c54d5c5b8e)

- rewrite deployment guide for developer-friendly Azure Functions experience (62680345a4ff5c8ab2eb88b54e7237d5f5c173ba)

- add sample CLI output excerpt to README (#124) (d0a480d5845a2fa4a4679bd501346937edaa9424)

- add deployment guide with diagnostics-first workflow (#122) (36a95b88a3c70176e33bc2d359278b40598cb847)

- Merge pull request #121 from yeongseon/docs/issue-120-ecosystem-positioning

docs: add ecosystem positioning and design principle (76f5f459ca24cfc08a87206197643956a0dd81c7)

- align terminology with Oracle review (07aaeb0a578dcecd8ce364347459a3b486850722)

- add ecosystem positioning and design principle (4c2d7a56d70f4afc87c86a48c6a61651c2f06939)

- Merge pull request #119 from yeongseon/fix/mermaid-fence-div-format

fix: switch Mermaid fence format to fence_div_format for rendering (939de1179f56c73ded198820a7028056f8422cc4)

- switch Mermaid fence format to fence_div_format for rendering (0c3f4cc5262ea81051274693413ef459469e461e)

- Merge pull request #117 from yeongseon/docs/fix-mermaid-rendering-116

docs: enable Mermaid diagram rendering on GitHub Pages (2245e8eae3cf4d26985daff01e7f622321a77856)

- enable Mermaid diagram rendering on GitHub Pages (9806343339ae377f44e73900f615224600773382)

- standardize section order and fix factual inaccuracies (#115) (d2515966804e950e13dee19a35143c267e3991dd)

- standardize architecture docs with Mermaid diagrams, Sources, and See Also (#113) (cb1fdd784ffdf779ebca00d65550037052938073)

- use platform-aware candidate map for executable_exists (#107) (2dc2c2934e7f2c095290d15f1ef1f8e4505176aa)

- fall back to python3 when python is not on PATH (#105) (ffa38d5becade5c983df051cec1be3059e42857e)

- add automatic GitHub Release creation on tag push (#103) (09476576f1b7b37bb75b5c1caf3393850f7c8a9a)

- add release process to AGENTS.md (dda2bfaa5d653168fb9e257f7539e316b1468967)
## [0.16.2] - 2026-03-29

- Merge pull request #102 from yeongseon/chore/release-v0.16.2

chore: release v0.16.2 (2878efb29f2b80fe6bc512cd4e7aaa2546ad0601)

- release v0.16.2 (f5bdf8ecba15b91d4eeba844c7837218d32a816d)

- resolve 6 confirmed bugs (#95–#100) (#101) (e6d1957d0487c79d3dd956759a27beb5f792f19c)

- use standard pypi environment name for Trusted Publisher (64f4af308b1f7646c9223d75dae40e7ac17a4c84)
## [0.17.0] - 2026-03-22

- update README with Azure Functions Python DX Toolkit branding (96c95bfb668fe4abc0abf21700e9eaf974df8026)

- Merge pull request #92 from yeongseon/chore/rename-environment

chore: rename publish environment from production to release (dccea9ee2cd495f47281397f53040cb348438693)

- rename publish environment from production to release (a5fe2d1883d5fd022cf05780a4906017bf4e5331)

- Merge pull request #91 from yeongseon/chore/unify-workflows

chore: unify CI/CD workflow configurations (896994e7922b4912b810296a7327b0b41233170d)

- unify CI/CD workflow configurations (91afa2412dc123dee0d95dacce1e24f8587408a0)
## [0.16.1] - 2026-03-21

- Merge pull request #82 from yeongseon/release/v0.16.1

chore: release v0.16.1 (9cac09263d1faa0530bfacd46c67b03a601ae8e3)

- release v0.16.1 (91855b3fb9b129c7274a81d3d9093baa827d5228)

- add make build to AGENTS.md validation, standardize .gitignore (#81) (1b7a5b4c4c849a0e1622eaf523365674159e71cc)

- fix ruff version, coverage threshold, Black→ruff in docs, pre-commit refs, mkdocstrings version (#80) (26946ec0e41b7725791cb170d09bda51f6e56a43)

- trigger e2e only on release tag push (v*) (34cb1081f969d17fee3f8b6504dc24e1828fa542)

- add real Azure e2e test section to testing.md and CHANGELOG (0693bd05502a8afdf489495133469ea8a96bdbc3)

- upgrade GitHub Actions to Node.js 24 compatible versions (bce19f78048a46d3ce471142e48b91661700623c)

- correct AuthLevel.Anonymous → ANONYMOUS and add restart step for function discovery (4c97b845210f39de6303f7536679d44d9d201374)

- add post-deploy wait and status probe for Consumption cold-start diagnosis (ea5a4cf17bd40224037cebd5e69391f5c681132e)

- extend warmup timeout to 300s for Consumption plan cold starts (3d933accd11eb84d2bdf2bd2b31c50cd53136e3d)

- fix e2e warmup to wait for 200 instead of non-5xx (7c729188c3eacc272e08c5d31be7f00afefc992b)

- add --no-cov and pytest-html artifact to e2e workflow (d87104a2e06b0621177d830f231cb6ce1ad64128)

- add real Azure e2e tests and CI workflow (cc90f1ffa410a7f95773765969d9054b87420fee)

- add extended handler registry coverage tests to reach 88% threshold (efaad96106b08bc57c08b71eac6fa15f6c0396d7)

- enforce coverage fail_under = 88 (b037459f248e0fe3c4c081d748e85e9746469ea7)

- add architecture.md and add to mkdocs nav (5e1ac7b3e678e579b95b817a59cd004cfdeccb81)

- add keywords to pyproject.toml (1ca665e75067e11ee46150fb8a79d848ea67478a)

- remove .venv-review from tracking, add to .gitignore (8832f9a2d5385f7176d60a2efc1e699660f20630)

- add AGENTS.md, Typing classifier, test_public_api, Dev Status 4-Beta (799d240ba806212a4c04e3ed4a54a47315c3eaff)
## [0.16.0] - 2026-03-15

- bump version to 0.16.0 (06730c43cc48fbd32e9f616fc1a9032e74a6b35c)

- add codebase and gap analysis documentation (bfc368a41fac64a434f62a5bb15f543bf9392687)

- map warn status to <skipped> instead of <failure> (23d1305678b5de09fc55ee12385fa0b3cfaea364)

- add scaffold integration guide (7bf9eec6f4796d68a0ab004db0ea956cd8f03d77)

- sync minimal_profile.md with current 5-rule required set (bf10505f2b0d966dd7a50cd53113256741ac3df2)

- add source metadata fields to core required rules (c4c32e591ea874ca78170c13b61193f07af85d53)

- add warning for azure-functions-worker dependency (baeaff7994149ce5c503d48dd01000ec3352ce17)

- sync diagnostics with current required flags (93c2655c58e2d1108d3fff05bf66b15cd6db352e)

- apply conservative MS Learn-based policy to core rule set (c621a83e8b4a65b460699edb3e22ad368d69a94a)

- overhaul v2 examples with complete project structure and expanded tests (9919e80c994c167d44485f05df3f3987d3089482)

- add local.settings.json security check and extension bundle v4 validation (ca8ca6b9ddd08912636ba9aea54ea58916948030)

- add continue-on-error to SARIF test and fix empty helpUri in SARIF driver rules (ab6db33228bb679b2daef1de6ec759de3e6e41d6)

- use relative URI in SARIF locations and fix action integration test (5728dc4fcdd742aaf72bf6473771a3c47cf9795e)

- add official GitHub Action, CI examples, and README repositioning (3191d8f0bd17b882cd5986c1c28b92e691bcd2ba)

- change preflight workflow trigger to workflow_dispatch only (c9c1d63e86a9583750dd0903195658c178169e30)

- correct CLI invocation in preflight workflow (doctor subcommand) (cdd7fc953d6d4a055dcc282f42842d22078eab4f)

- harden diagnostics and expand rule coverage (1906b94e4ef48bc1088b0ba188ff6ab71b578e1e)

- add codex agent guidance (98dee22e9402190b0cd6dbc4e9a263df95126184)

- unify CI workflow patterns with canonical validation repo (e251581c7c9cfede3718cac45b977178fe394cb1)
## [0.15.1] - 2026-03-14

- bump version to 0.15.1 (bbe08e531792c28e6b1483a2256312240ce985fc)

- overhaul documentation to production quality (094663d1919981d116ab348df89eff5e0fb882df)

- sync translated READMEs (ko, ja, zh-CN) with English (b012ca6dbdf49a82fcea4b94ff848f8b9fefdc11)

- add project.urls to pyproject.toml (0be7f204cab941f6396cffc51077d4c49a5d7204)

- unify README — add Why Use It, rename Built-in checks to Features, rename Usage to Quick Start, add Ecosystem, remove Contributing, reorder sections (70184da2a8211a78fcd0bee10b89d436d7dd88ea)

- add example-first design section to PRD (4aedd537bd7efed144d4f3786dcc8bf0aef8856c)

- unify tooling — remove black, standardize pre-commit and Makefile (774bb984dd6deb9b81f4ee4e91026c04f399e798)

- expand thin pages with working Python code examples (595bf5121b8afcd67f64d5682934d75f42b4885a)

- elevate doctor documentation to production quality (ad7482ea3eae5ad96c396b6be0657b3a2708ed08)

- remove emojis from documentation and cliff.toml (22f9d4b0dbe080100cb90a1c85e632d93c1c4b8c)

- add badges and translated READMEs (ko, ja, zh-CN) (a1d49596e0cc7ca2832fc94b454105ffaf94c01f)

- add documentation pages and expand example fixtures (#73-#77) (0fafa5bd6425732ef2d944d40c5f02d0616482aa)

- update pre-commit hook versions and unify forbid-korean targets (a4ded23e3a8853ba7b2c9b9572d7439560269158)

- move disclaimer before license section (3238017a2f6660f5c805524e5a26f6240659cc2c)

- publish doctor releases from the production environment (5994bdcf7fe2dcda7e1e757581ecc304a7b96e71)
## [0.15.0] - 2026-03-08

- use trusted publishing for doctor releases (f855d1647f8090e661b946bfa8a8f5e7e122ba3d)

- make codecov uploads non-blocking (0a65920b62c4c1108278dc27722415fb56799506)

- stabilize func core tools resolution coverage (93fcaf045dbf73e5c062a9eb012231deb978cf15)

- move codecov token gating to the job env (8a21c8e571a9743d5171de55bb3133c28f65f13f)

- run the real doctor CLI in the demo (29dbfd4d0373c3ddfc299031e79ada9882c034c3)

- update changelog (669a07c86f290869ca6f291b4627a0e71566ccde)

- bump version to 0.15.0 (02cda2ae8437c80e537890cf44306a0bed906976)

- fix doctor workflow and docs build (e1360b8a911f94503f02172526e1be167c40efce)

- address valid review feedback on tooling and coverage (1a95da3c3ce12974b2000ff9aad6b480108767e0)

- support manual doctor releases (401d8eed3307da9b35db426bc7ec320ab83d506c)

- standardize repository planning documents (7b68765e45b5129c55c64de08b60bc5be85e5c17)

- slow down doctor demo and add final snapshot (b0f757893d72bf677aa9fcb719111c69339b68c1)

- fix doctor demo rendering workflow (a10e0378410e4470c480763f461c852ac2e30e66)

- use workspace-based doctor demo setup (75478dd1861ff55acfe43a02aae7092f60275796)

- refine doctor demo output (95a3da17365b65f20b9ff3fd35dff6d0fa2eb647)

- add README doctor demo (cf4fa6558d7b672147267de4a8ac5ae57be74914)

- document example coverage policy (a0e29e8780aad32b173755672e88d4b33d02e325)

- clarify doctor example coverage roles (e16da1470f2fcc529e746871cf914dd7dfe6e664)

- raise doctor coverage for utility paths (b0bb965f848459866fab0d37d1c64cfbdce4058a)

- cover doctor example projects (937a24fd933a938019dd3f6139728452c15b221e)

- pin doctor docs dependencies (7f758a02cf3e43a538b42383783d668c3675e5d9)

- chore: (7d8c5cecaf08bc91bf280ec428297d9d99546e35)

- apply remaining dependabot updates (2ff7fe3721b687246f578049b389d78ac3eeb340)

- Merge pull request #68 from yeongseon/dependabot/github_actions/actions/upload-artifact-7.0.0

chore(deps): bump actions/upload-artifact from 6.0.0 to 7.0.0 (1b601575ef9f827d613f86a397a0b4d8d2ab16e1)

- Merge pull request #71 from yeongseon/dependabot/pip/black-26.3.0

chore(deps): bump black from 26.1.0 to 26.3.0 (a5e8409c347def2e92831a4ba5409e94e6f6619d)

- update doctor branding and README badges (8bda49f6ac5a416fe81281f26c41c3ffe8a20093)

- align mypy checks across CI and pre-commit (75e1b84695e86359dcc7e5f623f8e2495aac47ef)

- remove Azure Functions Python v1 support (9dcf66f68b44d253c6aad14439709122a99f9ee5)

- align tooling and repository maintenance (95aa270675885f782bcc4cbbafe196147dd887f1)

- migrate forbid-korean hook to pre-commit stage (78efd58d86ea8341b92198dbbf65ee6eea7e9f20)

- run tests on stacked PRs by removing base branch filter (ceb52f3a61bb0a4d6f3aded0aebea610536d701a)

- Replace deprecated utcnow() with timezone-aware datetime.now(UTC) (4bfc8df269e17c5a0d23887bcfbac0266fcb392a)

- avoid reloading rules in CLI (879af4c82e84a82e154d8b67db4a7597c57645bb)

- document trust assumption for custom rules (Fixes #40) (6ec4ce0c0f96c392f628e680387fc4af3dbdc688)

- deduplicate file iteration in source_code_contains (Fixes #39) (7fce3bcbc8c2b94c8647ffd81936dee829b4e948)

- use Path consistently in handlers (Fixes #38) (2c5ff462b8115df13919a9fe5539ec68fa792bd8)

- use Path consistently in path_exists and file_exists (Fixes #38) (a3e6c4fe1b149b53175c79bddbd134c5698f8d30)

- document Config as reserved for future use (Fixes #37) (312492b5ec2f88c6543f1efe3e062e80e080ac98)

- implement issues #6, #15, #16 (6bc0454524a19349f378f44f3a5871d8b1510d5f)

- Merge pull request #23 from yeongseon/feat/validate-rules-runtime

Validate rules.json at load time (3fe1355bdace66a63238dddd7bab6625b27d3708)

- Merge main into feat/validate-rules-runtime (ea9f160f6fb0e97429f08dea6a1462562adf732f)

- Merge main into feat/validate-rules-runtime (b6173021e5d2bdca45a82ef3d86aad1934e62b6b)

- Merge main into feat/validate-rules-runtime (a417f5f3fac9184907e807d25319a84a31a4caf2)

- validate rules.json against schema (ff3b0f11655960144738619ab72ecf78c0d9a34d)

- Merge pull request #22 from yeongseon/fix/rules-schema-source-contains

Align rule schema with source_code_contains (5648c7890cdbc947835e1ccd18e0cae9309eeda1)

- Merge main into fix/rules-schema-source-contains (a1036d86f8c4d54e52d36698adae8d9d04ea2811)

- Merge remote-tracking branch 'origin/main' into fix/rules-schema-source-contains (a0cdba209a29991b8fb06df4dfcf2caadfde1275)

- align schema with source_code_contains (d66b3bd89faa6df291e8e0c4a48c7ee5383800b4)

- Merge pull request #32 from yeongseon/feat/custom-rules

Add custom rules.json option (488a5d05959c675113bd7cacb05452c2bdf9784b)

- Merge main into feat/custom-rules (72a71adcc36b86cac51abb8345da9a7fc946d580)

- Merge pull request #31 from yeongseon/chore/precommit-hook

Add ruff-format to pre-commit (a507193e714118b36529d2db23311180cf2d3255)

- Merge remote-tracking branch 'origin/main' into chore/precommit-hook (5890f177a8a0fa9e5646747634474d1537fa7a1e)

- add ruff-format pre-commit hook (6d79008084999f9645cc1789fff2b5b72eb423f8)

- Merge pull request #21 from yeongseon/fix/local-settings-rule

Fix local.settings.json rule condition (58a1d24f5b366b03375dd3abe4e78ebf1eeef046)

- Merge main into fix/local-settings-rule (e9079dac35f040aaf4166315b84714b30e1ee600)

- use condition.target for local settings rule (13dace0d4750fdf9881eb80f469ab35edacc7562)

- Merge pull request #24 from yeongseon/test/rules-schema-consistency

Add rules/schema consistency tests (905107e348c77fae9a983ae4091f37aaade82b2e)

- Merge main into test/rules-schema-consistency (37e95a309ea10b166364894204dd9bf29401b8f8)

- add rules and schema consistency checks (92f48f85a0275ea03afd04df41109e8258e9f246)

- Merge pull request #25 from yeongseon/docs/align-implementation

Align docs with current implementation (16f23c560f65336476c9ae4921320364d8575966)

- Merge remote-tracking branch 'origin/main' into docs/align-implementation (62dd35ca9dc1b06a34d1d45a5b1d2059627fac1d)

- align rules and dev guide (67c6bf1a6f088fedbca4e62297310f06eec031bb)

- Merge pull request #26 from yeongseon/feat/exclude-source-scan

Exclude common directories from source scan (3b640a183f4fbdd06a30c1f404b3c8b1b84742a0)

- Merge remote-tracking branch 'origin/main' into feat/exclude-source-scan (7e8d3e1fe67d91a9af4229472f4db1731722f4e2)

- skip common directories in source scan (b729c7cc1304c4fce37154e778abf542915a6ee1)

- Merge pull request #27 from yeongseon/feat/error-context

Add error context logging for handlers (1f34c191d7f9d4ea564e3fefddb8dea6ed96109a)

- Merge main into feat/error-context (9b9de07fb6424770bce1f243613f9bf77ab8053f)

- log handler and resolver failures (9d50c862b1645684d7befb6768cfc05c62795b08)

- Merge pull request #28 from yeongseon/chore/makefile-improvements

Normalize Makefile targets (cf098ffe11179f324b17db3f07fe554590a7ed09)

- Merge main into chore/makefile-improvements (9061871ad8f65ab1317f29c05bd1abc9414ca5cf)

- normalize Makefile targets (9a61bf0ab4b11108aed318dc8918fa67df3ba03e)

- Merge pull request #30 from yeongseon/chore/deps-upgrade

Upgrade dev tool versions (b6342f600534e5e01215ee5ab7265cd996192c8f)

- Merge remote-tracking branch 'origin/main' into chore/deps-upgrade (fef8e4f63f91c26c03c4ba70f3eafa9d0393fe07)

- bump dev tool versions (63dcd424f3032a3eba36b7aa8fc9891bc3ba1d4f)

- Merge pull request #33 from yeongseon/feat/json-metadata

Include metadata in JSON output (546af6579f42e5a2a6965e8c34beb4a797ec20e4)

- Merge main into feat/json-metadata (9a6a9ba227fa37c44e93a69c4237844493d78b22)

- add metadata to JSON output (db68eeda28a1e2064c783cb8704e757d343b1f53)

- Merge pull request #35 from yeongseon/feat/rule-profiles

feat: add minimal rule profile (02c4b7bb2b1c5faf54f1554150248b54c83648d7)

- Merge main into feat/rule-profiles (67b9903d1b09e6b194fdd182cbad4638618ddf8e)

- add minimal rule profile (08b53bed82ed092ebada604ff57bf2089eeadf29)

- Merge main into feat/custom-rules (0d0dcef617b07d8d8bba3bf02d01b77cd75bcc15)

- Merge pull request #34 from yeongseon/feat/sarif-junit

Add SARIF and JUnit output (fe04a752bdfeeadaf08c22bf3dfa36ad6334fc17)

- skip pytest imports in mypy (1b8a91c8f881a1269fe25485668abcbfc55dde17)

- skip pytest typing errors (916c16bceccedba45ff7fb78c1334ded85b2462f)

- Merge main into feat/sarif-junit (3efe287460f481cfc8177f4f9b0a022cfb96c828)

- translate remaining Korean to English and enforce no-Korean hook (a8957774fd03584742080fec0aa91b0b7888ec79)
## [0.14.0] - 2025-09-19

- update changelog (3490ecacf06a7ab83c8f83728f59e41591f1eac3)

- bump version to 0.14.0 (bf16918e69ed0ba42d832434bcaea0d3c9048834)

- bypass hatch and build mkdocs directly in CI (89cbf52d6f84c80eef0fc657523542498f90d8f2)

- drop hatch usage and run tools directly (adabf3ea0917c719d6f3d99ce95fbd18a3e11988)

- use existing hatch 1.9.4 and simplify env creation (1ca38d2a10dd2407ea997fb8c98792c3edb3f89f)

- pin hatch & skip pre-commit in CI env (859eb6d8d2e8020ac0af66aea36e9eaa8c22b5e4)

- skip pre-commit install in CI (b1ba3ebdebaa7eef3d27bb777c16056279a44e52)

- correct indentation and typing for package_declared handler (d7768207bc95a420301c7ba1ab6643a0c851fe06)

- require 'azure-functions' instead of deprecated 'azure-functions-python-library' (ad4bec2b431e81ef98c0d349dd812147bdd57b3c)
## [0.13.0] - 2025-09-19

- update changelog (d70a51bff1ddbcb3cfdac09b3c9aa4e9b128de3b)

- bump version to 0.13.0 (95fef3a1e1123bde297c8215a37a52e57470b0f1)

- align CLI tests with strict fail exit semantics (a7b60c3d03549b956c09cfb9ee79d10c5113e931)

- exit with code 1 when fails present and document semantics (a8e38ed7e741fc68ccb9993ceb096978d0019191)

- summarize fails instead of errors without changing exit behavior (f07b16b18f51bd4c38b80689d0408b5cdaa4a7da)

- add v1 multi-trigger sample (http, timer, queue) (e3ea509270d2c2a1f8f374096d6892e942b26f4e)

- rename v1 HttpExample to http-trigger and update docs (beda5550be8ec97eaec829aa24d62b00d58161e1)

- rename v2 basic-hello to http-trigger (8a8e0f23b82fd970f9148b39556ff308fbb714de)

- remove duplicate examples/v1/basic-hello (734cf38c076b4b0d640fe19d75c3c8dff3956a48)

- add installation steps and CLI usage (d9eff0d1a711705943830885e58725e2bd90efad)

- remove deprecated examples/basic-hello (2c2ecd854a4f31d715868bdd669adf4218cf1560)

- split examples into v2/multi-trigger and v1/HttpExample; update docs (c423686945ee3b1247d72d08537976862fcea6f6)

- bump version to 0.12.0 (f47589ae0d6d228041441b81b008c72e30f7c782)

- remove severity field and simplify status model (BREAKING) (3ad0bbc016e1e714010448f67a14ae4bbb6f7b71)

- update usage examples and README for concise messages (03938076cd61823210a4e639ba1001c9bb3937cb)

- shorten executable_exists detail (e.g. 'func detected') (d4e84af95aea624aeceb04b8cf6682689b9dce41)

- unify status icons to README set (✓ ! ✗) (e6316fc717e49f88944fac382ecbee7de52576a1)

- simplify compare_version detail string and update test (ee99799cc177ac678557de10f27bd4bf4d3427f2)

- unify status icons using format_status_icon for JSON output and errors (e784df6e78178f2248e95d9d822b034f4e54708f)

- add icons & status legend (pass/warn/fail) (101644291175c7c3b30c507a514d634dcfab6c2f)
## [0.11.0] - 2025-09-07

- update changelog (6a122dcd3351e3933514c33bfbd3027cb0397890)

- bump version to 0.11.0 (9b64954b1ed7f1ad8fbc9c37fdecf759c6f17f1a)

- merge handler tests into single file; remove duplicate; add type hints (f1367558997e6a2630ac4496157683cd23a2bf59)
## [0.10.0] - 2025-09-06

- update changelog (f6f40e2f48cbaa0fff33bea600480ec61d72aba5)

- bump version to 0.10.0 (2979e22dc658b0cf2f1b0266a58f4ba9ddebc6b8)

- update CLI name references and use new example screenshot filename (ec953a1e677e1e28ed3693ed24e813b56f24357a)

- accept 'jsonpath' in Condition TypedDict (fix mypy) (cbcf52850cdd1f86823008baaf267ee22d40f81c)

- rename command to 'azure-functions doctor' and update UI; doctor: include severity metadata and normalize statuses (7b327f9f9dbceb5afc13e6d090be14f1daccadc3)
## [0.9.0] - 2025-09-06

- update changelog (7c01e2cba5f71ebd4326bc8a441e4a81d278bf76)

- bump version to 0.9.0 (6cf33bc61cb2c8256f1eff52295292ae365d256b)

- replace 'func-doctor' with 'azure-functions' in docs and examples (30057fce6f80fba9e5a4d15dcdbc795823a9b90f)

- update CLI tests to use 'doctor' subcommand (25423c5fb1ea81f3a6401cb9a6f0bfbb9adce300)

- rename subcommand to 'doctor' and add 'azure-functions' console script entrypoints (7101e7f92ecb25f3c9d382674048bb94adc628c7)
## [0.8.0] - 2025-09-06

- update changelog (c0cb87053d831b1003518e78768f4645ee570dc7)

- bump version to 0.8.0 (52b07238fbc699434e615e00b7828ab06e5dbe82)

- Run formatters (black/ruff) adjustments (1895c63c1d014ba42b6c8e2d899c9178227637f1)
## [0.7.0] - 2025-09-05

- update changelog (31e2c19f216b44d7a60c33e31cbad87e3561fad4)

- bump version to 0.7.0 (f1a3ebb19a11194282a9e86222174fd89aedfff7)

- merge new handler tests and update programming model/rule-loading tests (019d875570b245ff787e8b73e72097df32cdfb11)

- simplify rule loader, add allow_v1 flag for CLI (c0d52982df13a70587afa67509bb4bf3e80bf4ae)

- add conditional_exists and callable_detection handlers (428b59fbdca4e3151cd8410eb60ee957b1024d34)

- add v1/v2 rule stubs and severities (fcbe157ac2c3246b9171a56b4ee5075ca89dfc89)

- add Severity column to v2 programming model checks (ad021874bc78d42369346f81a2c9b4d7e9bdf0f6)
## [0.6.0] - 2025-09-05

- update changelog (ffc692f5465f58c8816e9ff28d2e7841d5a5196e)

- bump version to 0.6.0 (f6bad63d9cfd913b6bb6461c9fc8ca8d53ae70eb)

- update legacy rules.json for backward compatibility (a9ba697213ebe60570d701c53c91ce064ada4afb)

- update documentation for v1/v2 programming model support (c7653652bb4045cd624cb6d6b521fa1500103900)

- improve UI and add v1 project support with warning (fd04e11d825d34d7fa6a25816712f25ce7ad1328)

- implement separate rule sets for v1 and v2 programming models (2bb5952602e2d63e9676bb383958b1d6aec0c8e2)

- implement programming model detection for v1 and v2 (568f756521cb6657bcf6a12617a9872bd074bedd)

- bump version to 0.5.1

- Fix verbose option behavior
- verbose now only controls hint display, not logging level
- Update CHANGELOG.md with fix details (a6a8690e8f5ac10e9092d2783ecba200403f5caa)

- separate verbose option from logging level control (9b373a91243fcf5668afec8491beea95b258fa7d)
## [0.5.0] - 2025-09-03

- update changelog (deeb342676ef59776d8812758b64632bc730e9ee)

- bump version to 0.5.0 (248da2a31fa91b09270d72627a2d20569526360d)

- improve error handling and robustness (1c90078671dbee99ce13d3c0a1920447bcfc141f)
## [0.4.1] - 2025-09-03

- bump version to 0.4.1 (a9fc413faef0efb421ce93cafcc267bb349ada39)

- unify output using Rich Console (ebaf2071df99d2f61eb34a8940ff5e386176a134)

- bump version to 0.4.0 (a21ca7cb94a14e29eb2d3f5d5abb3aaeb35d2bc0)

- add v1/v2 compatibility check at initialization (af3621b35dcef7513839f8e0b8f07b329cf82a9a)

- mark local.settings.json implemented; test: assert optional local.settings.json passes (ab2c16d5dfdab13720a66bf539c61998a0bc8dc6)
## [0.3.0] - 2025-08-30

- update changelog (1fef4982e53a40df6ac191e8d11aea3607d1d015)

- bump version to 0.3.0 (cb009efdfbae834ee293973df6346c8251e34e90)

- fix documentation build issues (df9046675e4cb25d4f0d1f9e754a034d63c42aa1)

- resolve diagnostic failures and pre-commit issues (cc2a27eedd63c0dbf6d0c35ab2ca93a98b7bf26b)

- implement major code structure improvements (18c3d60ef104003ebc93788a25db5e7fcc34b0cd)
## [0.2.0] - 2025-08-30

- align local version with PyPI release (0.2.0) (68a011cfc517751eda20de5b19d9a1f378296187)
## [0.1.11] - 2025-08-30

- update changelog (afdf7359dafaf8ff444552b08152a5d9cd25271b)

- bump version to 0.1.11 (39be13cfef2f5725f46766d897c4b822504b20fc)

- remove overly ambitious roadmap document (3a9d4d15b45709d6a68e77d22939f3288a8bfae8)

- add comprehensive roadmap for static analysis and CI/CD platform (66db758d6d426b0bd76fdcb7d76c2fac60b165b0)

- add architecture diagram and remove emojis from README (654c34195bd21ed502218bd12624843ce1fb89db)

- enhance open source documentation and add contribution templates (2a7a811e19d1394982b88643145196a7c13883f9)

- implement centralized logging infrastructure (8b508c585e54b825fde4456fd53bc995c2e41652)

- Merge branch 'main' of https://github.com/yeongseon/azure-functions-doctor-for-python (40194d23ffe4160319e0d8c428b366e1760c5274)

- Merge branch 'main' of https://github.com/yeongseon/azure-functions-doctor-for-python (3459db77278e4d0a1a1a337b9e13e9fe804ad4aa)

- update changelog (01d9c94bc3adba61f4921df9aee69ef063623e4c)

- refine sarif and junit outputs (4f288d7f3e289affb104ed446190b2f67a780910)

- add SARIF and JUnit output (b1b674ef96fa2d757e5376586496b7988dd6b004)

- allow custom rules file (ee260411fca40d350d265477f993a195cb5dad49)

- update changelog (67f7d2ea5e2eed122f41f527659e650f12f6614d)

- bump version to 0.1.11 (7fdb1e6c480d4e20497e497a152c2d1b55c85b05)

- add version check target (29bcbed13943e78c5fcc817be11af8a2dd2ceec4)

- update release process guide to reflect hatch-based workflow (d0a814cd6222723180a3d10d6f7051041bfb2917)

- configure default and test PyPI repositories for hatch publish (931563cf2e6d5b463863fed12f7ffe0da79443b9)

- add publish-pypi and publish-test targets for PyPI release (f769088317f3e23dafaf4b0f3b3aa90ab98db31a)
## [0.1.10] - 2025-06-22

- bump version to 0.1.10 (e7b53af13a317f886e95c88d3c5cce26a5e36ba0)

- use Hatch inside virtualenv with automatic bootstrap (e2bec3f660a7366a3255888bde1a519756bfa523)
## [0.1.9] - 2025-06-03

- update changelog (95e1596371c72e478a87a1d06846b14fa8877bb9)

- bump version to 0.1.9 (5c6af020db3e59dd6ce32e6285aefd6381f8e8c3)

- rename CLI command from azfunc-doctor to func-doctor in docs and scripts (ecbd0320830548de7c74dfb48ab9dccb636c0974)

- update README and documentation for improved usage and structure (cae2b7191443d747d4ca3ec44a513b15b155e7cb)

- replace screenshot with lowercase filename for azfunc-doctor example (1bbf2e1db358d47508a6d3a69ba40f3063507ce8)

- improve README usage section with clearer structure and sample image (2af7acbe4c389aaf79890dbdcf3422beb41f1192)

- simplify changelog template to fix template errors (8bf9f9905508a44d4ad8e384ca670ce34e0036f3)
## [0.1.8] - 2025-06-02

- update changelog (a973c03fb168c8b2df2231260dba9a030f6310e1)

- bump version to 0.1.8 (a339eb5cf40530e8b64a50ec5e8cb88db1453ed2)

- fix packaging path and changelog format issues (fb98bd2333be27ae023a7f62083f8468cf4640be)
## [0.1.7] - 2025-06-02

- update changelog (1dbd7c5fc35cad09b973b524fea8fd7ef3e46a02)

- bump version to 0.1.7 (726b7b6d6f515327b4058ae10a602dcb90067f1a)

- remove unnecessary wheel target config for src layout (b1b8e60a37b4d11a8806bddc2f8a4ad598c3393b)

- fix ModuleNotFoundError by adding src to pytest PYTHONPATH (9e2b07136523a3ffeabfddec1263521918dd344b)
## [0.1.6] - 2025-06-02

- update changelog (047381f9717d6989ed81f3c08dc06c29ea83dee1)

- bump version to 0.1.6 (4261829476f5868ecabd103cea5cff926fec7a48)

- replace 'import' with 'target' in package_installed condition (1ab3d0aa88019688f7c515248899828535818e7e)
## [0.1.5] - 2025-06-02

- update changelog (f5485f8a54eb91bca222a081ff8bb6837e9b5f0f)

- bump version to 0.1.5 (18b397efb41e1ea0f198a8be5295c4f11843dc42)

- add __init__.py to assets for package recognition (7a1c6547f0d873a309ed9f6097cd157fc3a350c4)

- add unit tests for generic_handler including new rule types (c9cdede1f25868dd5928f80f0380614307d25a17)

- update tests to load rules.json from embedded package resources (695eb65c51a6184cd519860587c39b98f3a011b3)

- add 'source_code_contains' rule type and improve rule handlers (1ed6f7be63a5638c8b2fca1ca97a4598d0058059)

- load rules.json from package resources using importlib.resources (8af58a3caeead16090cdd93934fe65d8027fb4f9)

- move rules.json to package assets and update pyproject.toml include path (030fcee105a32d875f3eccfaa941400229e4a623)

- update diagnostics list for Python Programming Model v2 (be5f16a14b82869287753ef05e6702c4e7913b0a)

- update CI badge to match renamed test.yml workflow (a8d8ec356aedc4d0cf3b8671c264b167b799972b)

- rename CI workflow to test.yml (89cd70df618fceacbab2af6740164d1c842f002d)

- add Codecov upload step and coverage badge (663e0db6bb7eb514bc8ed0de94d5c522cda06502)

- fix diagnostics tests by copying rules.json into temp directories (7f61ea91a393ed127000af7f0c746ed08f46b9b6)

- move rules.json to project root and update loader path (35d76849728f45aaef0d2b2d643f12a641696eda)

- add packaging dependency for Windows CLI compatibility (30e0161ab33e5bf33211fdf0cf22f40be2989f72)
## [0.1.4] - 2025-06-02

- update changelog (a1765777b493cc5cba2a7ddb548762659588f0dc)

- bump version to 0.1.4 (dfc1a2aeec65297d5a91fa42a7a1eded1a196ad2)

- fix packaging path and add missing dependency (40ae5e2d04a0362dffec03d5ac3992ad8565ee22)
## [0.1.3] - 2025-06-02

- update changelog (3df3a2eb351dc39ba81d287902f48d3e08b6eae1)

- bump version to 0.1.3 (340053cea4359e2156a3269d04ecae5345b2c041)

- add automatic commit after version bump in release targets (69ba5da761dcd850ad96f9eb792b37a3b762e9b4)

- correct wheel target package path for src layout (86239d9c10037f2ec4aa635a108f42e5764c6888)
## [0.1.2] - 2025-06-02

- bump version to 0.1.2 (4b1546283c0351c2fd5ad967452b39120564e7c9)

- update changelog (9dd6ebda32c8be419179331643cf8e17350380ef)

- remove unsupported commit.remote from git-cliff template (9f429fb328962d93492fce6f2aca50ec3e44ca92)

- separate version bump from release logic to avoid duplicate version update (3a3e1c24292b7c11d67ab6eaff4632a0add8b37d)

- sync tag and version, improve Makefile release steps (e97ec207204058e1ef7b2eefbf76e9b7d5c61b21)

- declare version as dynamic in pyproject.toml for PEP 621 compliance (41cc80d3005fcd24280533a66f7eda8b046b6ced)

- update README badges for CI and release workflows (628f8a7e21317f3ba744dde10da99a9ef5b47852)

- consolidate changelog for 0.1.1 and clear unreleased (07cfb5df5ecaf91c5e632a25774a037cc11e753d)

- generate changelog for v0.1.1 (d96c275d907f28f696f6128d7431b04e21ba86a8)

- switch to dynamic versioning and fix Makefile targets (7cdee62a6f7fe7a8a2f7220ae0a41a602b54403f)
## [0.1.1] - 2025-06-02

- update changelog (916ee3d1b4d643192a9bcad2896a1b8d498c6482)

- update changelog (0b116f48d48621bb35b70543be1ba19786671ac3)

- use twine for PyPI upload on tag push (9af1dbe7778fd2c301e4ce48848285a902f86538)

- trigger PyPI publish on tag push (054d22632b406b5874f7240208654ca56b4840b5)
## [0.1.0] - 2025-06-02

- reflect latest commits in CHANGELOG.md (bd094b00f7d5fe646d1b1f830e3adbb05fefbe8b)

- update PyPI classifiers to include Python 3.11 and 3.12 (7115bd5eb1783331d7becc723f15f92e962852f8)

- fix project name to 'azure-functions-doctor' across all files (4559727181598a2aa2af8cc3f527eda237fd1501)

- add GitHub Actions release workflow (48a45485064bc599e58ab8be63eb25e0dcfc8ce0)

- update changelog (4f1a1e658bd5705e85b1d9ccc058fdab11305e83)

- add changelog for v0.1.0 (2f9a0d00f273445314da3e2999a84010e4a5084c)

- update README for basic-hello with Python model v2 instructions (44e332998ce0935271a5f93f65d584289b89bd9e)

- add release process guide and git-cliff config (0984e73a19e2c814acfcbc178deee46876f9f66b)

- add changelog generation and release process to Makefile and docs site (7ebb433982852fbfe754d6830c1324eaf3bf2f77)

- fix packaging path and add metadata for PyPI (682ccc13226967caa1e46e0f43bf0a7849ae6edd)

- update logo assets with new design (2bf4fa1bd6f2a77186bd65adc1568ba7176ef280)

- add GitHub workflow, PyPI, coverage, license, and download badges to README (4d67eedb274af56ba76d68523958c7dad31bc89f)

- update mkdocs.yml to reflect new repository name (ce2b9515d5d97d884c6450ab5c9c7e8aae8d0c36)

- enlarge logo in README and finalize CLI doc structure (fb7a695b14a1e592d7b8393960a4e4e879cac65b)

- Merge branch 'main' of https://github.com/yeongseon/azure-functions-doctor (083cbe6af7cff4d559597eab35f4c8339c5f36f4)

- enlarge logo size in README for better visibility (fd9445c68b1d832420b0278389a61792d48970e1)

- enlarge logo size in README for better visibility (f8f6d9c0fdb14cef6a65d8dbeb7e964c8c02c16a)

- update README and add relocated logo_assets directory (c81e1424557d04812f63e78ab8deaea0beae2826)

- update README and remove old logo assets (9e19f37a161cfbf632f73f6894039e885a447deb)

- update CLI usage, main docs, and add CONTRIBUTING guide (884199ff408540d9ad52794ac7641ce6fe4eaed2)

- add official logo assets for Azure Functions Doctor (a69d52e77296937184e35fc4ac239f14024469f5)

- update project title and links for renamed repo (bb6f59afef6106ae91bae9c23672bb20c03ce074)

- restructure rule logic and output handling (cf49aef15c37d549d2275d6303a93c8e025e9f28)

- Configure docs environment and ensure Python 3.9 compatibility (982387b0753091a1ed1f3b6e4500e104bcaa7ff6)

- Add MkDocs config, Makefile target, and GitHub Pages deployment workflow (47b935ae36e9c2e8338a454a2a1f156770afd42e)

- integrate API auto-documentation using mkdocstrings (e59e3ef61e1a27c32ea0fbac6e1578d9622d2713)

- restructure check logic and improve test coverage (1a2709c9f03fb6b2492159d4005bf232a45b9770)

- Modularize check logic and add handler registry (21f4f0f118e2dff7593f6b3624657a0c1bb5d66d)

- update main README with installation, usage, and example links (310a437331cfb5211897c09f50a06d6400cbb8ba)

- add README for basic-hello Azure Function example (bce8b849e73e7236e1948e23f6baaedf80eceefd)

- add basic hello world Azure Function (HTTP trigger) (659362e063ed33745a552fceaa0b7d8afb0303be)

- update development and usage guides (8e262c92567a27b94d426d3cf09ead74ba4a5dab)

- fix artifact upload conflict by including Python version in name (d8fdca4e8f47a4827a60fb3d3a218f02d886a41b)

- rewrite CLI tests using subprocess to verify full entrypoint (41b02e4faddb622d2ecd67dafe91fcdf163ac01d)

- improve diagnose command with rich output and verbose option (27f9cc259b30097840a9155b44c9d1c007b1c45a)

- increase line length limit from 100 to 120 for Black and Ruff (7e9808e4fdb567a634ea6bd97deca6e9aebb0fba)

- organize pyproject.toml and include py.typed for PEP 561 support (eab6e83360a1134893ecff15523874d48b8b1c9e)

- add modular checks and API compatibility with diagnostic output (fd98178733cd08c27e85a53849065c8e2b81a54a)

- modularize doctor checks and standardize diagnostic result format (692eb93a4a9df51e5e16351befab049c999d9782)

- update diagnostic checklist with unified table and official references (ed64d6e7a682a49176a0ce35877422bed7718480)

- explicitly register diagnose command and fix CLI entrypoint (e41ed3548d29140c801b57c2d0abdb1a2727ceaf)

- migrate CLI from Click to Typer (253e8c047be3d65cfd4a97bf7f8ee358bc547101)

- pin tool versions and unify configuration (bb49a027ee23abe8750f25363cdff8975bc083c4)

- improve Hatch environment and pyproject.toml structure (f1a33615598bb90c3c1dfb6af7c8520b2f4aafd2)

- migrate to full Hatch-based workflow with unified Makefile and CI (8127be701f006fb22be094eb4b1233ec16c54b5b)

- add CLI usage, development guide, and diagnostics roadmap with mkdocs config (779384836e773f016f4a3fc06c77f028e6815d66)

- add commitizen configuration and Makefile targets for patch/minor/major (ee464494be83929343ec749180fc2cd84dc25590)

- add initial changelog with current features and setup history (4652ff36bf36321d6398e5e00a98b4d7b2b2c9cb)

- migrate CLI from Typer to Click and fix typecheck/lint issues (e7482b6ca27885db50125f19778755dc7e051ecb)

- remove .tox and htmlcov in Windows clean-all script (483f5c5656acbcab4d7700fa9fbe7a832f13ce50)

- prevent NUL file creation on Windows when checking for uv (3eee166f5376d43d0e0f6c6792b95f7b2e5cb751)

- extract Windows clean commands into scripts (3a063b806168e5f09242e84275c3ecec5341ef35)

- update pyproject.toml configuration (e12a26300588a189bdc37f70c1a9a485e7e1b2e8)

- add module-level and function docstrings (7ee433ab4f9cb35877e8ec82e00068cc0decc574)

- add tox target for multi-version testing (13bbef209db339bfa4df3713d1efec8d170806a0)

- configure tox environments in pyproject.toml (0adb6ad2d065aa349d1d0629a42ca21641e3a6de)

- add cross-platform uv detection with pip fallback (285454d5828f11f1e240a7887b5b246f047b5aa7)

- fix missing venv setup in GitHub Actions with uv (6a01121a52b4a5a94a19f6ab58d846af36b550a0)

- fix missing venv setup for uv-based environment (f912cbb6fd34266a4b3ebaa9c2b14bc5179c7b00)

- clean up tool configs and improve Makefile portability (c73237982ef1cb3bd73808b43367d7bbc59a3790)

- update README to reflect renamed package path (2af0995e215ab28099b0afb50356c98904579997)

- update site name in mkdocs config to match new package name (5e05007611c5074f659c6cce093f3d35add55ea7)

- update module name in documentation to azure_functions_doctor (206132cd430685977c4f9ebd406516b45fc9a1d3)

- update coverage config to match renamed package (35cb199d434d7e47c625f23c9fa612eab945018f)

- update hatch build path to match renamed package (10d17bd6f177cdb2acdd366a923110d2dc24b139)

- update pyproject.toml for renamed package and mypy/ruff config (3b11ad1f0160f2a92615c86458c1db117c030c3f)

- rename package from azure_function_doctor to azure_functions_doctor (92783158cc044f7074afc94a5582807f793bf9c8)

- update .editorconfig for markdown and YAML handling (27100660adcc0bbd7babf4ff9d942e4cb39238ce)

- add .editorconfig for consistent code style (f69d3e3ee8f375664fe22f63e9091d9578b78919)

- finalize dev environment setup and update documentation (1e932f8becbc00cdd9d42b3168b4711bd80259e8)

- convert test_doctor to pytest format (4a3acec18f495c1727812447fb31f69fe4c86863)

- add pre-commit, coverage, and CI configuration (329d8a78a2e3f984aafb67798686c82997901c17)

- add hatch-based release and publish automation (b08c1b69a1ccfcbd08b656af0d26592c564dbb83)

- migrate to pytest and update Makefile test command (a9f54096802786c57bbb32073ff023344d77a4c2)

- apply full initial setup with CLI, testing, and formatting tools (153aa236852935e6be5cad498f3bb2004b6cec77)

- initial project setup with CLI, Makefile, docs, and packaging (a39efbd9a2d2b953905b6ce3925badab2b44c117)

- Initial commit (457425ebde591e34042116d1e5f92ac7006a03cd)

