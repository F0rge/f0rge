# POPIA, PAIA, ECTA and CPA: what the DasKasas website must do

> This is research, not legal advice. Have a South African attorney review it before DasKasas relies on it.

Researched 2026-11-21 for DasKasas (Pty) Ltd: a Bedfordview showroom plus a Medusa online shop. The data processors are Clerk (auth, US), PostHog (analytics, EU/US), SendGrid (email, US), Railway (hosting, US/EU) and Paystack (cards, Nigeria/SA).

**How each source was checked**

- **Act texts** come from the Government Gazette PDFs on gov.za: POPIA (GG 37067), ECTA (GG 23708), CPA (GG 32186) and PAIA (GG 20852). Current wording was confirmed against SAFLII's consolidations:
  - **POPIA:** updated to 1 February 2022 and never substantively amended. Only commencement notices exist.
  - **PAIA:** updated to 11 October 2024. s51 was rewritten by POPIA s110 from 30 June 2021.
  - **ECTA:** updated to 1 December 2021. s45 was repealed by POPIA s110 from 30 June 2021, and s49 now points to the National Consumer Commission.
- **Regulations:** POPIA Regulations GN R1383 (14 December 2018), as amended by GoN 6126 (GG 52523, 17 April 2025). CPA Regulations GN R293 (1 April 2011). PAIA Regulations GN R757 (27 August 2021).
- **Regulator material:** Information Regulator pages and PDFs on inforegulator.org.za, and National Consumer Commission (NCC) statements on thencc.org.za.

**Confidence labels.** Unlabelled items are confirmed in an Act or Regulation. **[Guidance]** marks Information Regulator or NCC publications, which are advisory and not law. **[Secondary/unverified]** marks claims confirmed only from commentary, or not confirmed at all.

## Summary

1. **POPIA privacy notice (s18):** the notice must be shown *before* collection whenever data comes straight from the customer. That covers account sign-up, checkout, newsletter, contact form and the analytics banner. It must name the cross-border transfers and give the Information Regulator's contact details. Since the 2025 regulations, it must also state the right to object (Reg 2.4).
2. **Marketing email, SMS, WhatsApp or push needs opt-in consent (s69).** A pre-ticked or opt-out box does not count: Reg 6.4 says "opt-out shall not constitute consent". The only exception is the existing customer. It applies when DasKasas got the contact details through a sale and markets its own similar goods. It also requires a free chance to object at checkout and in every message.
3. **Time-sensitive: the CPA opt-out registry is now live.** CPA Amendment Regulations were gazetted on 15 April 2026. Per the NCC, direct marketers must register with it, and the registration window runs from 15 September 2026 "until December 2026". From May 2027 marketers must also clean their lists against the registry before each campaign. **The gazette text itself was not retrieved; only NCC statements were.** If DasKasas will send any marketing message, register now and confirm the duties against the gazette.
4. **Analytics consent (cookies):** POPIA has no cookie rule. No Regulator cookie guidance was found. Analytics identifiers are still "personal information" ("online identifier", s1), so POPIA's notice, lawful-basis and objection rules apply.
   - The Regulator's direct-marketing guidance lists "use of cookies" as a form of electronic direct marketing. That makes advertising and retargeting tags opt-in in practice.
   - Prior consent for plain first-party analytics is best practice, not a stated legal requirement. The current #757 design meets it: consent-gated, cookieless, PostHog EU.
5. **Every processor needs a written contract (s21) and a transfer ground for data leaving SA (s72).** For payment and order email, "necessary for the performance of a contract" (s72(1)(c)) works. For hosting, auth and analytics, rely on a binding agreement with adequate protections (s72(1)(a)), meaning the vendor's DPA, or on consent. Vendor DPAs were not reviewed.
6. **Information Officer:** the CEO or managing director is automatically the Information Officer, or someone they authorise in writing. They must be registered on the Regulator's eServices Portal before taking up duties (s55(2)). The Regulator says non-registration is not itself an offence, but the head of the company then carries the liability.
7. **PAIA manual: no exemption is in force.** The last ministerial exemption (GeN 397, GG 44785) expired on 31 December 2021, and the Department of Justice called it final. No later notice was found up to November 2026. DasKasas must:
   - publish the manual on its website;
   - keep it at its principal place of business;
   - supply it on request, and to the Regulator on request.

   Wilful or grossly negligent failure is an offence (PAIA s90(3)).
8. **The website must show the ECTA s43(1)(a)–(r) items.** Checkout must allow the customer to review, correct and withdraw the order before it is placed. If either is missing, the customer gets a 14-day cancellation right (s43(3)). That right applies even to goods the s44 cooling-off excludes.
9. **CPA presentation:**
   - Terms limiting DasKasas's liability, shifting risk, or making the customer "acknowledge" facts must be conspicuous, in plain language, and shown *before payment* (s49). A link to the terms is not enough.
   - If they are not, the term is unfair by definition (s48(2)(d)(ii)).
   - The customer must get a free copy of the terms with an itemised breakdown of what they owe (s50(2)(b)).

---

## 1. POPIA

### 1.1 Notification when collecting (s18)

**Contents of the notice.** s18(1): the responsible party "must take reasonably practicable steps to ensure that the data subject is aware of":

- [ ] **(a)** the information collected, and its source if it was not collected from the customer.
- [ ] **(b)** "the name and address of the responsible party". Use the full legal name, DasKasas (Pty) Ltd, and the showroom or registered address.
- [ ] **(c)** "the purpose for which the information is being collected". List purposes per form: account, order fulfilment, delivery, payment, marketing, analytics.
- [ ] **(d)** "whether or not the supply of the information … is voluntary or mandatory". Mark required versus optional fields.
- [ ] **(e)** "the consequences of failure to provide the information". For example, no delivery without an address.
- [ ] **(f)** any law authorising or requiring the collection, such as tax record-keeping. Confirm which laws with the accountant.
- [ ] **(g)** any intended transfer "to a third country … and the level of protection afforded". Name the US, EU and Nigeria, and say what protection applies. See §1.4.
- [ ] **(h)** "any further information" needed to make processing reasonable:
  - (i) recipients or categories of recipients: Paystack, SendGrid, Clerk, PostHog, Railway, couriers, the maker or supplier;
  - (ii) the nature or category of the information;
  - (iii) the right of access and the right to rectify;
  - (iv) the right to object under s11(3);
  - (v) the "right to lodge a complaint to the Information Regulator and the contact details of the Information Regulator". Use the block in §1.7.
- [ ] **Right to object.** Reg 2.4 (2025 amendment) makes the right to object mandatory at collection. The responsible party "must, when collecting personal information … notify the data subject … of their right to object".

**When to give it.**

- [ ] **Direct collection.** s18(2)(a): "before the information is collected, unless the data subject is already aware". Engineering consequence: a visible privacy-notice link (or summary) on every form *before* submit. This covers Clerk sign-up, checkout, newsletter, contact and the analytics consent banner.
- [ ] **Indirect collection** (e.g., data from a courier or a supplier). s18(2)(b): before, "or as soon as reasonably practicable after it has been collected".
- [ ] **No repeat needed for the same purpose.** s18(3): a notice already given covers later collection of "the same information or information of the same kind if the purpose … remains the same". A new purpose means a new notice.
- **Exceptions.** s18(4) lists them. Consent to non-compliance, no prejudice, and "not reasonably practicable" are the ones that could matter here. Do not design around them.

### 1.2 Security (s19), operators (s20–s21) and breaches (s22)

**s19(1).** DasKasas "must secure the integrity and confidentiality of personal information … by taking appropriate, reasonable technical and organisational measures to prevent" loss, damage or unauthorised destruction, and unlawful access or processing. s19(2) requires DasKasas to:

- [ ] (a) identify "all reasonably foreseeable internal and external risks". Keep a short risk register covering the database, admin accounts, API keys, backups, staff devices and the showroom POS.
- [ ] (b) "establish and maintain appropriate safeguards". Examples: least-privilege admin roles, MFA, encryption in transit and at rest, secrets management, backups.
- [ ] (c) "regularly verify that the safeguards are effectively implemented". Examples: periodic access reviews and restore tests.
- [ ] (d) "ensure that the safeguards are continually updated". Examples: dependency patching and incident follow-ups.
- [ ] s19(3): have "due regard to generally accepted information security practices". No specific standard is named.

**Operators (processors).**

- [ ] **s21(1): written contracts.** DasKasas must, "in terms of a written contract", ensure each operator "establishes and maintains the security measures referred to in section 19". Get a signed or accepted DPA from Clerk, PostHog, SendGrid, Railway and Paystack, plus any courier or maker that receives customer data.
- [ ] **s21(2): breach notice from operators.** The operator "must notify the responsible party immediately" of suspected unauthorised access. Check that each DPA says so.
- **s20: operator confidentiality.** Operators may process only "with the knowledge or authorisation of the responsible party" and must treat the data as confidential.

**Breaches (s22).**

- [ ] **Who to notify.** Notify the Regulator and the affected data subjects "as soon as reasonably possible after the discovery of the compromise" (s22(1)–(2)).
- [ ] **How to notify the Regulator** [Guidance]. The Regulator says that "As of 1 of April 2025" notifications must be made on its eServices Portal (https://eservices.inforegulator.org.za).
- [ ] **How to notify customers.** In writing; email to the last known address is allowed (s22(4)(b)). The notice must include the possible consequences, DasKasas's measures, recommended steps for the customer, and the attacker's identity if known (s22(5)).

### 1.3 Direct marketing by electronic communication (s69), and the CPA overlay

**Definitions.**

- **"Direct marketing"** means to approach a data subject "either in person or by mail or electronic communication" to promote or offer goods (s1).
- **"Electronic communication"** means "any text, voice, sound or image message sent over an electronic communications network" (s1).
- **Which channels count** [Guidance]. The Regulator's POPIA page lists email, SMS, telephone and "Push Notifications" as electronic communication. Its direct-marketing guidance also lists Instagram and LinkedIn DMs and "use of cookies" (para 7.1).

**The rule.** s69(1): direct marketing "by means of any form of electronic communication … is prohibited unless the data subject (a) has given … consent … or (b) is, subject to subsection (3), a customer".

**Prospects and newsletter sign-ups (consent route).**

- [ ] **One request only.** DasKasas may approach a person "only once in order to request the consent", and only if they have "not previously withheld such consent" (s69(2)(a)). Never email a bought or scraped list to "ask permission".
- [ ] **Form 4 content.** Consent must be requested "in the prescribed manner and form" (s69(2)(b)). The 2025 Reg 6.1 requires "written consent … on a form substantially similar to Form 4 or in any manner that may be expedient", including email, SMS and WhatsApp.
  - "Writing" now means writing under ECTA s12 (Reg 1.4, 2025), so a web form works.
  - Form 4's content: the responsible party's name and contact details; "Specify goods or services to be marketed"; the data subject's consent; and "SPECIFY METHOD OF PREFERRED COMMUNICATION".
  - Build the sign-up with a short description of what will be marketed (e.g., "new furniture, sales and showroom events"), a channel choice (email / SMS / WhatsApp), and an **unticked** consent control.
- [ ] **No opt-out consent.** Reg 6.4 (2025): "opt-out shall not constitute consent". The guidance note (para 7.3.3) adds that "silence cannot mean consent" [Guidance].
- [ ] **Record the consent.** DasKasas bears the burden of proof (s11(2)(a)). Store timestamp, channel, wording or version shown, IP or user-agent, and the source form.
- [ ] **Withdrawal at any time.** Consent may be withdrawn "at any time" (s11(2)(b)).

**Existing customers (no prior consent needed), s69(3).** DasKasas may market only:

- [ ] (a) if "the contact details … [were obtained] in the context of the sale of a product or service". A completed order qualifies; an abandoned cart or account-only sign-up is doubtful [analysis].
- [ ] (b) "for the purpose of direct marketing of the responsible party's own similar products or services". Furniture and décor to a furniture buyer fits. Third-party offers do not.
- [ ] (c) if the customer got "a reasonable opportunity to object, free of charge and in a manner free of unnecessary formality":
  - "(i) at the time when the information was collected". Put an opt-out choice at checkout.
  - "(ii) on the occasion of each communication". Every message needs a working one-click unsubscribe.

**Every marketing message (consent or customer route), s69(4).**

- [ ] Every message must contain "(a) details of the identity of the sender".
- [ ] Every message must contain "(b) an address or other contact details to which the recipient may send a request that such communications cease".
- [ ] **Suppression lists** [Guidance]. Keep a database of people who withheld consent or objected, and never contact them (Direct Marketing Guidance Note, para 7.3.5 and 6.4).

**Non-electronic marketing** (post, in person at the showroom). This is allowed without consent but is subject to objection at any time under s11(3)(b). Once someone objects, DasKasas "may no longer process the personal information" for it (s11(4)).

**What is not direct marketing [analysis].** Order confirmations, delivery updates and receipts are not direct marketing because they do not promote goods. A back-in-stock alert the customer asked for is solicited. Abandoned-cart reminders, "you might also like" emails and promotional push notifications are direct marketing.

**CPA overlay (applies in addition to POPIA).**

- [ ] **CPA s11.** Every person may "refuse to accept", "require another person to discontinue", or "pre-emptively block" direct marketing (s11(1)). A marketer "must implement appropriate procedures to facilitate the receipt of demands" and must not market to anyone who has demanded it stop or "registered a relevant pre-emptive block" (s11(4)). No fee may be charged (s11(5)).
- [ ] **CPA s12 and the 2011 notice on prohibited times.** There must be no direct marketing "directed to a consumer at home" on:
  - "Sundays or public holidays";
  - "Saturdays before 09h00 and after 13h00";
  - other days "between the hours of 20h00 and 08h00".

  The exception is where the consumer agreed otherwise. Marketing may not be "timed to be delivered" in those periods unless "expressly, in writing, agreed to". Schedule campaign sends in SAST inside those windows. **[Secondary/unverified]:** commentary on the 2026 amendment suggests the times may have changed, but this was not confirmed.
- [ ] **CPA 2026 opt-out registry.** Status:
  - **Primary [Guidance, NCC]:** the NCC confirms that the Minister gazetted the Consumer Protection Act Amendment Regulations, 2026 on 15 April 2026, making the NCC the registry administrator. Its launch statement of 7 October 2026 sets out the phases:
    - **Registration:** "opened to direct marketers for registration from 15 September 2026 and until December 2026". Failure to register after that "may constitute a contravention of section 11".
    - **Free list-cleansing:** "December to April 2027".
    - **Consumer blocks:** effective "from May 2027".
  - **Penalties [Guidance, NCC, 17 April 2026]:** up to R1 million or 10% of turnover.
  - **Not verified:** the regulation text itself (GG 54521, GoN 7380 per the gov.za listing) was not retrieved. The gov.za page attaches an unrelated PDF.
  - **Not verified:** the details of the monthly-cleansing duty and fees.
- [ ] **CPA Reg 4(3)(g) (2011), already in force.** "except in respect of those existing clients where the direct marketer has proof that the existing client has … expressly consented", a direct marketer "must assume that a comprehensive pre-emptive block has been registered" unless the registry confirms otherwise. With a live registry, this makes **proof of express consent** worth having even for customers.
- [ ] **POPIA still applies to people not on the registry** [Guidance]. The Regulator's 21 April 2026 statement says POPIA compliance "is still mandatory, irrespective of whether a consumer … is registered".

### 1.4 Cross-border transfers (s72)

**The rule.** s72(1): DasKasas "may not transfer personal information about a data subject to a third party who is in a foreign country unless" one of these applies:

- (a) the recipient "is subject to a law, binding corporate rules or binding agreement which provide an adequate level of protection" that "effectively upholds principles … substantially similar" to POPIA and restricts onward transfers;
- (b) "the data subject consents to the transfer";
- (c) "the transfer is necessary for the performance of a contract between the data subject and the responsible party";
- (d) the transfer is necessary for a contract "concluded in the interest of the data subject" with a third party; or
- (e) the transfer is for the data subject's benefit and consent is impracticable.

**No Regulator adequacy list.** No list of "adequate" countries and no s72 guidance note was found on inforegulator.org.za.

**Proposed ground per processor [analysis; vendor terms not reviewed]:**

| Processor | Data | Where | Suggested s72 ground |
|---|---|---|---|
| Paystack | card payment, name, email | Nigeria / SA | If processing stays in SA, there is no transfer. Otherwise (c): payment is necessary for the sale. |
| SendGrid | email address, order emails | US | Order and delivery emails: (c). Marketing emails: (a) via DPA, or (b) consent captured at sign-up. |
| Clerk | account identity, email, sessions | US | (a) via DPA. (c) is arguable only for account features needed to buy. |
| Railway | whole database and backups | US/EU | (a) via DPA. Hosting is not "necessary for the contract" in the s72 sense. Prefer an EU region and a DPA with onward-transfer terms. |
| PostHog | consented analytics events | EU (US possible) | (a) via DPA, plus the analytics consent. Pin to the EU host. |

- [ ] For each processor: a DPA that requires POPIA-equivalent safeguards and restricts onward transfer. This covers s72(1)(a)(i)–(ii) and s21.
- [ ] Disclose the transfers and the protection level in the s18 notice (s18(1)(g)) and in the PAIA manual ("planned transborder flows", PAIA s51(1)(c)(iv)).
- **Prior authorisation (s57(1)(d)).** Transfers of *special* personal information or children's data to a non-adequate country need prior authorisation. A furniture shop should not be processing either, so keep it that way.

### 1.5 Data-subject requests: access, correction, deletion and objection (s23–s25, s11(3))

**Access (s23).** A customer "having provided adequate proof of identity" may request:

- [ ] (a) confirmation, "free of charge", of whether DasKasas holds their information;
- [ ] (b) "the record or a description of the personal information … including information about the identity of all third parties, or categories of third parties, who have, or have had, access". The answer must come "within a reasonable time", "at a prescribed fee, if any", "in a reasonable manner and format", and "in a form that is generally understandable". Keep the processor list current so a request can be answered.
- [ ] **Fees.** If a fee applies, give "a written estimate of the fee before providing the services" (s23(3)(a)).
- [ ] **Tell them about correction.** When access is given, tell the customer about the right to correction (s23(2)).
- **Refusals.** Refusal grounds are PAIA's (s23(4)), and the rest must be disclosed if part is refused (s23(5)).

**Correction and deletion (s24).**

- [ ] **Scope.** A customer may ask DasKasas to "correct or delete personal information … that is inaccurate, irrelevant, excessive, out of date, incomplete, misleading or obtained unlawfully", or to destroy a record DasKasas may no longer keep under s14 (s24(1)).
- [ ] **Response.** DasKasas must act "as soon as reasonably practicable", tell the customer what was done (s24(2), (4)), and tell earlier recipients where the change affects decisions (s24(3)).
- [ ] **2025 regulations: free, any channel.** Correction and deletion requests are free "at any time" (Reg 3.2–3.3). They must be accepted "by hand, fax, post, email, SMS, WhatsApp message or in any manner expedient" (Reg 3.4). Telephone requests must be recorded (Reg 3.5). The customer must be notified "within thirty (30) days" of the action taken (Reg 3.6).

**Manner of access (s25).** PAIA s18 and s53 apply to s23 requests. A private body must decide a PAIA request "as soon as reasonably possible, but in any event within 30 days" (PAIA s56(1)).

**Objection (s11(3)–(4)).**

- [ ] **What can be objected to.** Processing based on legitimate interests (s11(1)(d)–(f)), and direct marketing other than s69 marketing.
- [ ] **How.** Objections are free, may be made "by hand, fax, post, email, SMS, or WhatsApp" using a Form 1–like form (Reg 2.3). Telephone objections must be recorded (Reg 2.5).
- [ ] **Effect.** After an objection DasKasas "may no longer process" for that purpose (s11(4)).

**Engineering summary:**

- [ ] a privacy@ address (and the account page) accepting access, correction, deletion and objection requests;
- [ ] an identity check before disclosing data;
- [ ] a request log with dates;
- [ ] a 30-day SLA;
- [ ] an export of a customer's data across Medusa, Clerk, SendGrid and PostHog;
- [ ] deletion that propagates to the processors.

### 1.6 Information Officer (s55–s56) and registration

**Who.**

- POPIA defines the Information Officer of a private body as "the head of a private body" under PAIA (s1). For a company, the head is "the chief executive officer or equivalent officer … or any person duly authorised by that officer" (PAIA s1 "head", para (c)).
- **[Guidance]** Officers are "appointed automatically" by position (IO Guidance Note, para 5.1). An authorisation of someone else "must be in writing" (para 5.5.1), and the authorised person should be "at an executive level or equivalent" (para 5.9). The person authorising remains accountable (para 5.7).

**Duties.** s55(1) makes the Information Officer responsible for:

- [ ] (a) "the encouragement of compliance … with the conditions for the lawful processing";
- [ ] (b) "dealing with requests made to the body pursuant to this Act";
- [ ] (c) working with the Regulator on investigations;
- [ ] (d) "otherwise ensuring compliance";
- [ ] (e) any prescribed duties.

**Prescribed duties: POPIA Reg 4 as amended in 2025.** The Information Officer must ensure that:

- [ ] (a) "a compliance framework is developed, implemented, monitored and maintained" and "continually improved";
- [ ] (b) "a personal information impact assessment is done";
- [ ] (d) "internal measures are developed together with adequate systems to process requests";
- [ ] (e) "internal awareness sessions are conducted".

The 2025 amendment deleted Reg 4(1)(c), the PAIA-manual duty, and Reg 4(2). The manual duty still applies directly through PAIA s51 (§3). The Regulator's POPIA web page still lists the old 2018 duties, so it is stale.

**Registration.**

- [ ] **Register before acting.** s55(2): "Officers must take up their duties in terms of this Act only after the responsible party has registered them with the Regulator."
- [ ] **How to register** [Guidance]. Register on the eServices Portal (https://eservices.inforegulator.org.za). The Regulator's POPIA page says "Individuals (Sole Proprietor), small businesses, and firms are also obliged to register".
- **If not registered** [Guidance]. The same page says: "It is not an offence for an organisation to not have an officer registered … the head of the organisation will be held liable."
- [ ] **Keep details current** [Guidance]. Update details "at intervals of not more than one year" if necessary. The details "contained in the PAIA Manual must be the same as the particulars provided to the Regulator" (IO Guidance Note, para 11.1–11.2).
- **Deputies (s56).** Deputy Information Officers are optional for a small body: s56(a) says "such a number of persons, if any".

### 1.7 Complaints to the Regulator (s74) and its current contact details

**The right.** s74(1): "Any person may submit a complaint to the Regulator in the prescribed manner and form."

**Channels.**

- The 2025 Reg 7.2 allows an "online complaint Form 5 available on the website", or Form 5 at the Regulator's offices.
- Reg 7.5 also allows fax, post, courier, or "email to a designated email address".
- [Guidance] The complaints page says users "must first register a user profile on our eService Portal and submit the complaint through the Portal".

**Contact block for the s18 notice** (s18(1)(h)(v)). From inforegulator.org.za, checked 2026-11-21:

> Information Regulator (South Africa)
> Woodmead North Office Park, 54 Maxwell Drive, Woodmead, Johannesburg, 2191
> P.O. Box 31533, Braamfontein, Johannesburg, 2017
> Tel: 010 023 5200 · Toll-free: 0800 017 160
> General enquiries: enquiries@inforegulator.org.za
> POPIA complaints: POPIAComplaints@inforegulator.org.za, or online via https://eservices.inforegulator.org.za
> Website: https://inforegulator.org.za

**Sources for the block:**

- The physical address, phones and emails come from the Contact and Complaints pages.
- The P.O. Box comes from the letterhead of the Regulator's 21 April 2026 media statement.

**Stale or inconsistent details on the Regulator's own materials:**

- Older documents give JD House, 27 Stiemens Street, Braamfontein. These include the 2021 IO Guidance Note, the direct-marketing guidance note and the January 2025 regulation amendment. That address is stale.
- The POPIA page's Form 5 description says "POPIACompliance@…", while the Contact page says "POPIAComplaints@…". Use the Contact page address.

---

## 2. Cookies and analytics: what the law says vs best practice

**What the law says.**

- **No cookie provision.** POPIA has no rule about storing or reading data on a user's device. There is nothing like EU ePrivacy art 5(3). No Information Regulator guidance note on cookies exists on its guidance-notes or POPIA pages (checked 2026-11-21).
- **Analytics data is still personal information.** The s1 definition includes "any identifying number … online identifier or other particular assignment to the person". Analytics tied to a device or visitor ID is therefore processing, and the usual rules apply:
  - **A lawful basis under s11(1).** Either consent (a), or "necessary for pursuing the legitimate interests of the responsible party" (f).
  - **Objection.** Processing based on (f) can be objected to at any time, free, through any expedient channel (s11(3)(a); Reg 2).
  - **Notice.** The s18 notice must be given "before the information is collected" (s18(2)(a)). In practice that means before the first analytics call [analysis].
  - **Transfers.** s72 applies if the analytics host is abroad. PostHog EU is abroad.
- **Marketing cookies are treated as electronic direct marketing** [Guidance]. The Regulator's Guidance Note on Direct Marketing (c. December 2024) lists "Use of cookies" among the methods of electronic direct marketing (para 7.1(h)). For that point it cites the UK ICO's PECR guide and the EU Article 29 Working Party opinion on behavioural advertising.
  - **Effect:** retargeting pixels and ad-network tags used to market to a person fall under s69 opt-in consent.
  - **Status:** the note says it "is advisory in nature" (para 11). It is still the Regulator's stated view.

**What is not required by law.** A prior-consent banner for first-party, non-marketing analytics is not an explicit requirement of POPIA or of any Regulator publication found. Legitimate interests (s11(1)(f)) plus notice and an objection route is a defensible legal minimum [analysis].

**Best practice (the current #757 design already does this):**

- opt-in before any non-essential analytics;
- reject as easy as accept, and withdrawal at any time;
- no identifiers stored before a choice is made;
- EU hosting;
- data minimisation.

The Regulator's own website runs a consent banner that stores analytics cookies "only with your consent". That is its practice, not law.

**Checklist.**

- [ ] Keep analytics consent-gated as in `757-consented-measurement.md`. Do not add ad or retargeting pixels without s69-grade opt-in consent.
- [ ] The privacy notice covers analytics: purpose, PostHog as recipient, the EU transfer, the right to object or withdraw, and Regulator contact details.
- [ ] The banner or footer links to the privacy notice before any choice.

## 3. PAIA s51 manual (private bodies)

**Required contents.** PAIA s51(1), as substituted by POPIA s110 from 30 June 2021, says "The head of a private body must make a manual available … containing":

- [ ] **(a)(i)** "the postal and street address, phone and fax number and, if available, electronic mail address of the head of the body"; and **(ii)** "such other information as may be prescribed". The 2021 PAIA Regulations (GN R757) contain no manual-content regulation in their table of contents, so nothing extra was found.
- [ ] **(b)(i)** "a description of the guide referred to in section 10, if available, and how to obtain access to it". This is the Regulator's PAIA Guide, updated October 2021, in all official languages.
- [ ] **(b)(ii)** the latest notice of records available without a request, if any. This is a voluntary description under s52.
- [ ] **(b)(iii)** "a description of the records of the body which are available in accordance with any other legislation". Examples: Companies Act, tax, VAT and labour records.
- [ ] **(b)(iv)** "sufficient detail to facilitate a request for access to a record … a description of the subjects on which the body holds records and the categories of records held on each subject".
- [ ] **(c)** POPIA content:
  - (i) "the purpose of the processing";
  - (ii) "a description of the categories of data subjects and of the information or categories of information relating thereto";
  - (iii) "the recipients or categories of recipients";
  - (iv) "planned transborder flows of personal information";
  - (v) "a general description allowing a preliminary assessment of the suitability of the information security measures".
- [ ] **Update it.** s51(2): "The head of a private body must on a regular basis update the manual."
- [ ] **Use the Regulator's template** [Guidance]. The template is "PAIA Manual Template: Private Body", dated 1 October 2021, with 10 sections. Its sections run from acronyms, purpose and Information Officer contact details through the PAIA Guide, records categories and personal-information processing, to availability and updating. The Information Officer details must match the eServices registration (§1.6).

**Where to publish.** s51(3): the manual "must be made available":

- [ ] "(a) on the web site, if any, of the private body". Link it in the footer next to the privacy notice.
- [ ] "(b) at the principal place of business of the private body for public inspection during normal business hours". Keep a printed copy at the showroom if that is the principal place of business.
- [ ] "(c) to any person upon request and upon the payment of a reasonable amount".
- [ ] "(d) to the Information Regulator upon request".

**Is a small private body exempt? No, not currently.**

- **Exemption power.** Only the Minister can grant one, "for such period as the Minister thinks fit" (s51(4), unchanged).
- **The last exemption.** GeN 397, GG 44785 of 30 June 2021, issued by the Minister of Justice under s51(4), exempted "any private body, except any company which" was:
  - not a private company; or
  - a private company with "50 or more employees" in a listed sector; or
  - a private company with turnover at or above the schedule amount (retail: R45 million).

  The exemption ran "for a period of six (06) months, from 01 July 2021–31 December 2021". A small DasKasas-sized (Pty) Ltd would have been exempt only until then.
- **Called final.** The Department of Justice's 29 June 2021 media statement on gov.za called it "a final exemption".
- **No later notice found.** No later exemption appears in the Justice Department's notice indexes for 2022–2025 (the 2026 index returned 404). None appears on the Regulator's GG Notices page, including its 2025 and 2026 entries.
- **Consequence.** The manual is required now. "A head of a private body who wilfully or in a grossly negligent manner fails to comply with the provisions of section 51 commits an offence" (s90(3)). The penalty is a fine or up to two years' imprisonment.

## 4. ECTA: online sales (Chapter VII)

**Scope.** Chapter VII "applies only to electronic transactions" (s42(1)). A "consumer" is a natural person who transacts "as the end user" (s1). Any term excluding these rights is "null and void" (s48). Complaints go to the National Consumer Commission (s49, as amended by the CPA).

### 4.1 s43(1): information on the website

A supplier selling online "must make the following information available to consumers on the web site where such goods or services are offered". The suggested placement is in brackets.

- [ ] (a) "Its full name and legal status". For example, DasKasas (Pty) Ltd, a private company [footer and legal page].
- [ ] (b) "its physical address and telephone number" [footer and contact page].
- [ ] (c) "its web site address and e-mail address" [footer].
- [ ] (d) "membership of any self-regulatory or accreditation bodies … and the contact details of that body" [legal page, if any].
- [ ] (e) "any code of conduct to which that supplier subscribes and how that code … may be accessed electronically" [legal page, if any].
- [ ] (f) "in the case of a legal person, its registration number, the names of its office bearers and its place of registration". Show the CIPC registration number and the directors' names [legal page].
- [ ] (g) "the physical address where that supplier will receive legal service of documents" [legal page].
- [ ] (h) "a sufficient description of the main characteristics of the goods" [product page].
- [ ] (i) "the full price of the goods … including transport costs, taxes and any other fees or costs". Show VAT-inclusive prices, with delivery cost known before payment [product page and checkout].
- [ ] (j) "the manner of payment" [checkout and FAQ].
- [ ] (k) "any terms of agreement, including any guarantees, … and how those terms may be accessed, stored and reproduced electronically by consumers". Use a stable, printable or downloadable terms page with a version identifier [checkout link and order email].
- [ ] (l) "the time within which the goods will be dispatched or delivered" [product page and checkout]. For lead times, see `research-made-to-order-law.md` §4.
- [ ] (m) "the manner and period within which consumers can access and maintain a full record of the transaction" [order email plus account order history; state how long the history is kept].
- [ ] (n) "the return, exchange and refund policy" [footer and checkout].
- [ ] (o) "any alternative dispute resolution code to which that supplier subscribes and how the wording of that code may be accessed" [legal page]. See open question 6 on the CGSO code.
- [ ] (p) "the security procedures and privacy policy of that supplier in respect of payment, payment information and personal information" [privacy notice, plus a payment-security statement].
- [ ] (q) minimum duration for ongoing or recurring supply [not applicable unless subscriptions are added].
- [ ] (r) "the rights of consumers in terms of section 44, where applicable". State the 7-day cooling-off right and its exclusions per product type.

### 4.2 s43(2): review and correct before ordering

"The supplier must provide a consumer with an opportunity (a) to review the entire electronic transaction; (b) to correct any mistakes; and (c) to withdraw from the transaction, before finally placing any order."

- [ ] Show an order-review step listing items, options (fabric and colour), quantities, delivery address and method, delivery cost, taxes and the total. The customer must be able to edit each and go back or cancel before the final "Place order and pay" action.
- **Consequence of failure.** If (1) or (2) is not met, "the consumer may cancel the transaction within 14 days of receiving the goods" (s43(3)). The supplier then "must refund all payments made by the consumer minus the direct cost of returning the goods" (s43(4)). This is separate from s44, and the s42(2) exclusions do not switch it off.

### 4.3 s43(5)–(6): payment security

- [ ] **Secure payment system.** s43(5): "The supplier must utilise a payment system that is sufficiently secure with reference to accepted technological standards at the time of the transaction". Paystack's hosted checkout means DasKasas never handles card numbers. Keep it that way, use TLS everywhere, and verify webhooks.
- **Liability.** s43(6): "The supplier is liable for any damage suffered by a consumer due to a failure … to comply with subsection (5)."
- **PCI DSS** is the obvious "accepted technological standard", but the Act does not name it [analysis].

### 4.4 s44 cooling-off and the s42(2) exclusions

**The right.**

- **s44(1)(a):** the consumer may "cancel without reason and without penalty any transaction … for the supply … of goods within seven days after the date of the receipt of the goods".
- **s44(2):** "The only charge that may be levied on the consumer is the direct cost of returning the goods."
- **s44(3):** a full refund is due "within 30 days of the date of cancellation".
- **s44(4):** the section does not prejudice rights under other laws.

**s42(2) summary.** s44 does not apply to electronic transactions:

- (a) for financial services;
- (b) by auction;
- (c) for "foodstuffs, beverages or other goods intended for everyday consumption" delivered home;
- (d) for services started with consent within the 7 days;
- (e) where the price depends on financial-market fluctuations;
- **(f) where the goods "(i) are made to the consumer's specifications; (ii) are clearly personalised; (iii) by reason of their nature cannot be returned; or (iv) are likely to deteriorate or expire rapidly"**;
- (g) for unsealed audio, video or software;
- (h) for newspapers, periodicals, magazines and books;
- (i) for gaming and lotteries;
- (j) for date-specific accommodation, transport, catering or leisure services.

For furniture only (f) matters. Whether a fabric-and-colour choice is "made to the consumer's specifications" is unresolved; see `research-made-to-order-law.md` §6.

- [ ] On product pages and at checkout, state per item whether the 7-day cooling-off applies, and the return cost rule (s43(1)(r)).
- [ ] Refund cancelled orders within 30 days, deducting only the direct return cost.

## 5. CPA: how terms must be presented

**Plain language (s22).** Any notice or document "required, in terms of this Act or any other law," to be given to a consumer must follow a prescribed form, or be "in plain language, if no form has been prescribed" (s22(1)).

- The test is whether "an ordinary consumer of the class of persons for whom [it] is intended, with average literacy skills and minimal experience" could understand it "without undue effort" (s22(2)).
- The test considers "context, comprehensiveness and consistency", "organisation, form and style", "vocabulary, usage and sentence structure", and "illustrations, examples, headings or other aids" (s22(2)(a)–(d)).
- No NCC plain-language guidelines under s22(3) were looked up in this pass.

**Notice of risky terms (s49).** The trigger is any notice or term that purports to:

- "(a) limit in any way the risk or liability of the supplier";
- "(b) constitute an assumption of risk or liability by the consumer";
- "(c) impose an obligation on the consumer to indemnify";
- "(d) be an acknowledgement of any fact by the consumer" (s49(1)).

How such terms must be presented:

- [ ] They must be "written in plain language" (s49(3)).
- [ ] Their "fact, nature and effect" must be drawn to attention "in a conspicuous manner and form that is likely to attract the attention of an ordinarily alert consumer" (s49(4)(a)).
- [ ] They must be shown "before the earlier of the time at which the consumer (i) enters into the transaction … or (ii) is required or expected to offer consideration" (s49(4)(b)). Online, that means before the Pay button.
- [ ] The consumer must get "an adequate opportunity in the circumstances to receive and comprehend" them (s49(5)).
- [ ] **Unusual or serious risks (s49(2)).** If a term concerns a risk "of an unusual character", one the consumer "could not reasonably be expected to be aware" of, or one that "could result in serious injury or death", the consumer must assent "by signing or initialling the provision or otherwise acting in a manner consistent with acknowledgement". Furniture examples: assembly instructions, wall-anchoring of tall units, and weight limits. Use a dedicated checkbox per risk [analysis].
- **Consequence of failure.** A term is unfair if "the fact, nature and effect of that term … was not drawn to the attention of the consumer in a manner that satisfied the applicable requirements of section 49" (s48(2)(d)(ii)).

**Implementation.** Above the Pay button, show a short "Before you pay" box in plain language. Cover the s49 items: deposit forfeiture, natural variation in fabric and dye lots, swatch or screen colour differences, lead-time estimates, and delivery-access acknowledgements. Pair it with an unticked "I have read these points" checkbox, link the full terms, and store the terms version on the order.

**Other CPA rules that shape the site:**

- [ ] **Free copy of written terms (s50(2)).** A written agreement "applies irrespective of whether or not the consumer signs". The supplier "must provide the consumer with a free copy, or free electronic access to a copy". The copy must satisfy s22 and "set out an itemised break-down of the consumer's financial obligations". The order confirmation email should include, or link to a frozen copy of, the accepted terms version, plus the itemised price, delivery, VAT, deposit and balance.
- [ ] **Prohibited terms (s51) are void (s51(3)).** Do not draft terms that:
  - "waive or deprive a consumer of a right in terms of this Act" (s51(1)(b)(i));
  - exclude liability for "gross negligence" (s51(1)(c)(i));
  - "falsely expresses an acknowledgement … that … no representations or warranties were made" (s51(1)(g)(i));
  - require the consumer "to forfeit any money … if the consumer exercises any right in terms of this Act" (s51(1)(h)(i)).
- [ ] **Unfair terms (s48).** No terms that are "excessively one-sided" or "so adverse to the consumer as to be inequitable" (s48(2)(a)–(b)). Regulation 44 gives an indicative grey list; see `research-made-to-order-law.md` §9.
- [ ] **Showroom sales only: price display and sales records.** Neither section applies where ECTA s43 applies (s23(1)(b), s26(1)(a)), so online sales are covered by ECTA instead.
  - **Price display (s23).** Every displayed item needs a price (s23(3)). The lower of two displayed prices binds (s23(6)(b)). An "inadvertent and obvious error" binds only until corrected and customers are told (s23(9)).
  - **Sales record (s26(3)).** The written record must show the supplier name and VAT number, address, date, description, unit price, quantity, totals before and after tax, and the tax amount.

---

## Not confirmed from primary text

- **CPA Amendment Regulations, 2026 (GG 54521, GoN 7380, 15 April 2026).**
  - Confirmed only through NCC statements of 17 April and 7 October 2026 and the Information Regulator's statement of 21 April 2026. These are first-party regulator publications, but the regulation text was not read.
  - Not verified: registration and cleansing fees, the exact monthly-cleansing obligation, and whether the s12 contact times changed.
  - Law-firm summaries (ENS, Werksmans, Webber Wentzel, Bowmans, via search results) were not relied on.
- **Commencement of the 2025 POPIA regulation amendments.** GoN 6126 says they are published "for implementation with immediate effect" (17 April 2025). The schedule's own reg 11 says they "commence on a date to be determined by the Regulator by proclamation". No such proclamation was found. This research treats them as in force.
- **Processor facts.** Vendor DPAs, data locations and onward-transfer terms for Clerk, PostHog, SendGrid, Railway and Paystack were not reviewed.
- **The Regulator's cookie statement** (Direct Marketing Guidance Note, para 7.1(h)) rests on foreign sources and is advisory.

## Open questions for a lawyer

1. Is DasKasas a "direct marketer" that must register on the NCC opt-out registry if it emails only its own customers under POPIA s69(3)? What exactly does GoN 7380 require, and by when?
2. Does the 2025 Reg 6.1 "written consent … substantially similar to Form 4" require the full Form 4 field set in a newsletter sign-up, or is a checkbox with goods, channel and the business identity enough?
3. Is first-party, consent-free analytics on legitimate interests (s11(1)(f)) acceptable to the Regulator? Or should the consent banner stay as the legal basis?
4. Which s72 ground should be used for Railway and Clerk? Does a vendor DPA modelled on EU SCCs meet s72(1)(a)'s "substantially similar" test?
5. Do the 2025 amendments to POPIA Regs 2–7 apply now (GoN 6126) or only after a proclamation (Reg 11 of the schedule)?
6. Is DasKasas bound by the Consumer Goods and Services Industry Code (CPA s82, CGSO)? If so, does it have to be disclosed under ECTA s43(1)(e)/(o)? This was not checked in this pass.
7. For the PAIA manual, what is DasKasas's "principal place of business": the Bedfordview showroom or the registered office?

## Sources

**Acts (Government Gazette, gov.za):**

- Protection of Personal Information Act 4 of 2013, GG 37067: https://www.gov.za/sites/default/files/gcis_document/201409/3706726-11act4of2013protectionofpersonalinforcorrect.pdf
  - Commencement: Proc R21, GG 43461 (22 June 2020): https://inforegulator.org.za/wp-content/uploads/2020/07/20200622-gg43461-rg11136-pr21-POPIAsections.pdf
  - SAFLII consolidation (updated to 1 February 2022): https://www.saflii.org/za/legis/consol_act/popia4o2013399/
- Promotion of Access to Information Act 2 of 2000, GG 20852: https://www.gov.za/sites/default/files/gcis_document/201409/a2-000.pdf
  - SAFLII consolidation (updated to 11 October 2024; ss1 "head", 51, 53, 56 and 90 read there): https://www.saflii.org/za/legis/consol_act/poatia2000366/
- Electronic Communications and Transactions Act 25 of 2002, GG 23708: https://www.gov.za/sites/default/files/gcis_document/201409/a25-02.pdf
  - SAFLII consolidation (updated to 1 December 2021): https://www.saflii.org/za/legis/consol_act/ecata2002427/
- Consumer Protection Act 68 of 2008, GG 32186: https://www.gov.za/sites/default/files/32186_467.pdf

**Regulations and notices:**

- POPIA Regulations, GN R1383, GG 42110 (14 December 2018): https://inforegulator.org.za/wp-content/uploads/2020/07/20181214-gg42110-rg10897-gon1383-POPIA-Regulations-1.pdf
- Amendment of POPIA Regulations, GoN 6126, GG 52523 (17 April 2025): https://www.justice.gov.za/legislation/notices/2025/20250417-gg52523gon6126-POPIA-Regulations-Amendment.pdf
  - Amended text, signed 21 January 2025: https://inforegulator.org.za/wp-content/uploads/2025/04/POPIA-2021-Regulations-FINAL-21-Jan-2025.pdf
- PAIA Regulations, GN R757, GG 45057 (27 August 2021; scanned, OCR'd table of contents and regs 1–8): https://inforegulator.org.za/wp-content/uploads/2020/07/20210827-gg45057gon757-PAIAregulations-1.pdf
- PAIA s51(4) exemption, GeN 397, GG 44785 (30 June 2021; scanned, OCR'd): https://www.justice.gov.za/legislation/notices/2021/20210620-gg44785gen397-PAIA-ManualExemption.pdf
- Department of Justice notice indexes checked for later exemptions: https://www.justice.gov.za/legislation/notices/notice2021.html (and `notice2022.html`–`notice2025.html`)
- CPA Regulations, GN R293, GG 34180 (1 April 2011): reg 4, and the notice on prohibited times for contacting consumers: https://www.gov.za/sites/default/files/gcis_document/201409/34180rg9515gon293.pdf

**Information Regulator publications [Guidance]:**

- POPIA page (Information Officer registration, direct-marketing FAQ, breach reporting from 1 April 2025): https://inforegulator.org.za/popia/
- Guidance Note on Information Officers and Deputy Information Officers (1 April 2021): https://inforegulator.org.za/wp-content/uploads/2025/07/Guidance_Note_on_Information_Officers_.pdf
- Guidance Note on Direct Marketing (c. December 2024): https://inforegulator.org.za/wp-content/uploads/2020/07/GUIDANCE-NOTE-ON-DIRECT-MARKETING-IN-TERMS-OF-THE-PROTECTION-OF-PERSONAL-INFORMATION-ACT-4-OF-2013-POPIA.pdf
- PAIA page and Manual Template for a Private Body: https://inforegulator.org.za/paia/ and https://inforegulator.org.za/wp-content/uploads/2020/07/PAIA-Manual-Template-Private-Body.pdf
- GG Notices index: https://inforegulator.org.za/government-gazettes/
- Contact and complaints pages: https://inforegulator.org.za/contact-us/ and https://inforegulator.org.za/complaints/
- Media statement on the CPA Amendment Regulations 2026 (21 April 2026): https://inforegulator.org.za/wp-content/uploads/2026/04/MEDIA-STATEMENT-REGULATOR-NOTES-PUBLISHED-GAZETTE-OF-THE-CONSUMER-PROTECT-ACT-AMENDMENT-REGULATIONS-2026.pdf

**Other first-party statements [Guidance]:**

- Department of Justice, "Information Regulator takes over PAIA functions…" (29 June 2021; "final exemption"): https://www.gov.za/news/media-statements/information-regulator-takes-over-paia-functions-south-african-human-rights
- NCC, "NCC welcomes regulations to curb spam calls" (17 April 2026): https://thencc.org.za/ncc-welcomes-regulations-to-curb-spam-calls/
- NCC, "NCC launches the national Opt-Out registry…" (7 October 2026): https://thencc.org.za/ncc-launches-the-national-opt-out-registry-to-curb-unwanted-direct-marketing/

**Related repo research:** `research-made-to-order-law.md` (CPA s17/s19/s20/s55–56/s62, ECTA s42(2)(f)/s44/s46, Reg 44) and `757-consented-measurement.md` (the analytics consent design).
