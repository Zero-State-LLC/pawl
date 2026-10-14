# Data rights and platform decisions (2026-10-10 PT)

Decided by Grok Bot on Danny's instruction (chat, 2026-10-10 18:38 PT: "answer the open questions yourself based on research"). Danny's stated leans matched the evidence in every case. Quotes were read from the primary sources on 2026-10-10 PT. This is a policy reading, not legal advice.

## D1. X (Twitter) posts: IDs only outside the private store
- Decision: public repos, fixtures and any table shared outside Zero State carry X Post IDs (and `https://x.com/i/status/<id>` links) only. No post text, no author handle, no `author_id`. Full text stays in the private SQLite source of truth and in private, non-shared tables only.
- `author_id` is dropped in validated and curated layers (not hashed, not kept).
- Cap: no more than 1,500,000 Post IDs to any one entity per 30 days.
- Sources: X Developer Agreement and Policy, "Content redistribution": "If you provide X Content to third parties, including downloadable datasets or via an API, you may only distribute Post IDs, Direct Message IDs, and/or User IDs ... you may not distribute more than 1,500,000 Post IDs to any entity ... within any 30 day period" (https://docs.x.com/developer-terms/agreement-and-policy). X "More on restricted use cases": hydrated content may be shared only by non-automated means, up to 50,000 objects per recipient per day, "and should not make this data publicly available (for example ... in a public Github repository)" (https://docs.x.com/developer-terms/more-on-restricted-use-cases).
- Open item: user IDs are allowed by X, but we drop them anyway (privacy, and no use case needs them).

## D2. Wiktionary: permitted, with attribution and share-alike
- Decision: enabled for the pilot. Each record keeps its source URL as the attribution link, license "CC BY-SA 4.0 (dual GFDL)". Any redistributed derivative of Wiktionary text must carry attribution and the same license. Raw page text is not committed to repos; it stays in the landing volume.
- Source: Wiktionary:Copyrights: "The original texts of Wiktionary entries are dual-licensed to the public under both the Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA) and the GNU Free Documentation License (GFDL)" (https://en.wiktionary.org/wiki/Wiktionary:Copyrights); Wikimedia Terms of Use, licensing section (https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use).

## D3. Urban Dictionary: off
- Decision: not collected by Firecrawl. Existing `ud_define`/`ud_wotd` discovery hits in the source of truth stay internal evidence and are never redistributed.
- Source: Urban Dictionary Terms of Service: contributors grant a license to "the Company" only ("you grant the Company an irrevocable, perpetual ... license"), and no license is granted to third parties (https://www.urbandictionary.com/tos.php).

## D4. Know Your Meme: off
- Source: Know Your Meme Terms of Service: "You agree not to use or launch any automated system, including without limitation, 'robots,' 'spiders,' or 'offline readers,' that accesses the Websites in a manner that sends more request messages ... than a human can reasonably produce" and a no-competing-use clause (https://knowyourmeme.com/terms_of_service).

## D5. Green's Dictionary of Slang: off
- Source: site footer "Digital edition © Jonathon Green 2026", with separate Terms and Conditions (https://greensdictofslang.com/). Copyrighted reference work with no open license.

## D6. Reddit: Crawl4AI only, titles only
- Firecrawl refuses reddit.com; the collector also refuses it. Reddit stays on Crawl4AI. The "titles only" rule is carried forward from earlier work; I could not find it written down, so Danny should confirm it.

## D7. Firecrawl pilot: approved and run
- Danny approved 50 Wiktionary scrapes under a 60-credit cap (2026-10-10 18:38 PT). Run 2026-10-10 18:38 to 18:43 PT. 50 credits used (balance 2201 to 2151, OBSERVED from the Firecrawl API).
- Firecrawl text is evidence only. It never sets a human ruling, verdict or disposition.

## D8. Databricks workspace
- No existing workspace found (box, vault, One Mind, Notion, Gmail). Databricks Free Edition fits technically (serverless only, Unity Catalog, one SQL warehouse 2X-Small, max 5 concurrent job tasks, one workspace), but its terms say it "may not be used for commercial purposes" (https://docs.databricks.com/aws/en/getting-started/free-edition-limitations). Zero State LLC is a company, so Free Edition is allowed only for non-commercial evaluation. Danny must decide: Free Edition for evaluation only, or a paid trial / Startup Program workspace for real use.
