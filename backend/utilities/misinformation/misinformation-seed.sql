
BEGIN;

TRUNCATE TABLE
    narrative_cluster_posts,
    narrative_cluster_matched_facts,
    narrative_cluster_key_claims,
    narrative_clusters,
    posts,
    incidents
RESTART IDENTITY CASCADE;

INSERT INTO incidents (id, name, is_active) VALUES
    ('inc_east_gippsland', 'East Gippsland fire complex',     TRUE),
    ('inc_grampians',      'Grampians National Park fire',    TRUE),
    ('inc_otway_ranges',   'Otway Ranges grass fire',         TRUE),
    ('inc_macedon_ranges', 'Macedon Ranges spotfire',         FALSE),
    ('inc_mornington',     'Mornington Peninsula scrub fire', TRUE),
    ('inc_dandenongs',     'Dandenong Ranges ember alert',    FALSE);

INSERT INTO posts (id, author_name, platform, content, ts, share_count, post_url, misinformation_risk_score) VALUES
    ('post_001', '@gippy_local',     'TWITTER',  'BREAKING: CFA has just ordered FULL evacuation of Bairnsdale CBD. Get out NOW. They aren''t telling you how close it really is.',                  '2026-01-22T06:14:00+11:00', 3450, 'https://twitter.com/gippy_local/status/1',                0.9),
    ('post_002', 'EastGippyAlerts',  'FACEBOOK', 'Friends in Bairnsdale — evacuation order is OFFICIAL. Authorities have been hiding the real distance of the fire. Share to save lives.',          '2026-01-22T06:52:00+11:00', 2820, 'https://facebook.com/EastGippyAlerts/posts/2',            0.9),
    ('post_003', 'u/bushfire_truth', 'REDDIT',   'My cousin in CFA says they pushed an evac order for Bairnsdale CBD this morning but the website hasn''t caught up. Spread the word.',             '2026-01-22T07:48:00+11:00', 1220, 'https://reddit.com/r/melbourne/comments/3',               0.8),

    ('post_004', '@firewatcher_au',  'TWITTER',  'Wake up. The Grampians fire didn''t start itself. Eco-greens blocked the burn-offs and now arsonists are doing the rest. CFA won''t say it.',     '2026-01-21T19:30:00+11:00', 3200, 'https://twitter.com/firewatcher_au/status/4',             0.7),
    ('post_005', 'TruthAboutFires',  'FACEBOOK', 'They''re hiding it again. Grampians fire = arson + decades of blocked fuel reduction. Don''t believe the official line.',                          '2026-01-21T20:15:00+11:00', 1540, 'https://facebook.com/TruthAboutFires/posts/5',            0.6),

    ('post_006', '@drive_vic',       'TWITTER',  'Princes Hwy between Bairnsdale and Lakes Entrance is COMPLETELY CLOSED. There is NO eastbound evacuation route. VicRoads is lying.',              '2026-01-22T11:05:00+11:00', 9100, 'https://twitter.com/drive_vic/status/6',                  0.7),
    ('post_007', '@gippsland_now',   'TIKTOK',   'POV: trying to leave Bairnsdale and the highway is shut both ways. Why is no one talking about this?? #vicfires',                                  '2026-01-22T12:40:00+11:00', 4370, 'https://tiktok.com/@gippsland_now/video/7',               0.7),

    ('post_008', '@coast_weather',   'TWITTER',  'Hearing whispers of a 3pm wind change pushing the Otways fire straight at Apollo Bay. BoM not saying it publicly but my source is solid.',        '2026-01-23T08:22:00+11:00',  310, 'https://twitter.com/coast_weather/status/8',              0.4),
    ('post_009', 'u/otway_resident', 'REDDIT',   'Anyone else heard the 3pm wind change rumour? My neighbour reckons BoM told her it''s coming but they''re holding the announcement.',             '2026-01-23T09:10:00+11:00',  155, 'https://reddit.com/r/geelong/comments/9',                 0.4),

    ('post_010', '@grant_help_vic',   'TWITTER',  'URGENT: Vic Govt $5000 emergency rebuild grant — fire-affected residents apply within 48hrs at vic-rebuild-claim[.]com',                          '2026-01-20T14:55:00+11:00', 5500, 'https://twitter.com/grant_help_vic/status/10',           0.7),
    ('post_011', 'BushfireSupportAU', 'FACEBOOK', 'The Victorian Government has launched a $5000 rebuild grant for fire victims. Apply here before the deadline closes!',                            '2026-01-20T16:20:00+11:00', 4200, 'https://facebook.com/BushfireSupportAU/posts/11',        0.7),
    ('post_012', '@reliefnow_au',     'TIKTOK',   'If your home was hit by the East Gippsland fires, you can claim $5000 from the state. Link in bio. Don''t miss it!',                              '2026-01-20T17:45:00+11:00', 2240, 'https://tiktok.com/@reliefnow_au/video/12',              0.6),

    ('post_013', '@halls_gap_watch', 'TWITTER',  'Big wind change overnight will turn the Grampians fire toward Halls Gap. CFA is being too quiet about this one.',                                  '2026-01-21T21:30:00+11:00',  210, 'https://twitter.com/halls_gap_watch/status/13',           0.4),
    ('post_014', 'u/grampians_hiker','REDDIT',   'Anyone in Halls Gap should be packed and ready — overnight wind shift incoming according to a CFA volunteer I know.',                              '2026-01-21T22:05:00+11:00',  105, 'https://reddit.com/r/grampians/comments/14',              0.3),

    ('post_015', '@aviation_au',     'TWITTER',  'Reports a Coulson 737 water bomber went down near the Grampians 30 mins ago. No official word yet. Praying for the crew.',                         '2026-01-21T15:10:00+11:00', 8400, 'https://twitter.com/aviation_au/status/15',               0.9),
    ('post_016', 'PlaneSpottersVic', 'FACEBOOK', 'Heard from multiple sources a large air tanker crashed in the Grampians today. Authorities silent. Will update.',                                  '2026-01-21T15:42:00+11:00', 5300, 'https://facebook.com/PlaneSpottersVic/posts/16',          0.8),

    ('post_017', '@locals_first',    'TWITTER',  'Mate in Mallacoota says looters hit three evacuated houses last night. Police nowhere to be seen.',                                                 '2026-01-22T20:14:00+11:00',  410, 'https://twitter.com/locals_first/status/17',              0.4),
    ('post_018', 'u/east_gippsland', 'REDDIT',   'Hearing more reports of break-ins around Mallacoota while people are at the relief centre. Anyone else seeing this?',                              '2026-01-22T21:08:00+11:00',  230, 'https://reddit.com/r/melbourne/comments/18',              0.4),

    ('post_019', '@helpgippsfire',     'TWITTER',  'Donate to East Gippsland fire relief: bsb 063-000 acc 12345678. Every dollar goes direct to families. RT please.',                               '2026-01-21T11:30:00+11:00', 6700, 'https://twitter.com/helpgippsfire/status/19',             0.7),
    ('post_020', 'GippsRecoveryFund',  'FACEBOOK', 'Official East Gippsland Recovery Fund is now live. Bank details in comments. Please share widely.',                                              '2026-01-21T12:15:00+11:00', 4100, 'https://facebook.com/GippsRecoveryFund/posts/20',         0.7),

    ('post_021', '@cfa_vic',           'TWITTER',  'Watch and Act issued for areas south of Bairnsdale. Monitor VicEmergency for updates.',                                                          '2026-01-22T07:32:00+11:00',  980, 'https://twitter.com/cfa_vic/status/21',                   0.0),
    ('post_022', '@vicemergency',      'TWITTER',  'Princes Highway between Bairnsdale and Lakes Entrance: OPEN with reduced limits. CFA traffic management active.',                                '2026-01-22T12:30:00+11:00', 1240, 'https://twitter.com/vicemergency/status/22',              0.0),
    ('post_023', 'u/halls_gap_local',  'REDDIT',   'Just got back from the CFA briefing in Halls Gap. Containment lines holding, no overnight wind change forecast. Don''t panic.',                  '2026-01-21T22:30:00+11:00',  320, 'https://reddit.com/r/grampians/comments/23',              0.1),
    ('post_024', '@bom_vic',           'TWITTER',  'South-westerly change for Otway Ranges between 4pm and 6pm today. Conditions easing afterwards.',                                                '2026-01-23T09:00:00+11:00',  540, 'https://twitter.com/bom_vic/status/24',                   0.0);

INSERT INTO narrative_clusters (id, summary, incident_id, spread_status, review_status) VALUES
    ('nar_001', 'False evacuation order for Bairnsdale CBD',                              'inc_east_gippsland', 'SPREADING_FAST', 'NEEDS_REVIEW'),
    ('nar_002', 'Arson conspiracy claims about Grampians fire ignition',                  'inc_grampians',      'GROWING',        'CONFIRMED_MISINFORMATION'),
    ('nar_003', 'False claim that Lakes Entrance Road is closed',                         'inc_east_gippsland', 'SPREADING_FAST', 'NEEDS_REVIEW'),
    ('nar_004', 'Unverified weather speculation in the Otway Ranges',                     'inc_otway_ranges',   'STEADY',         'NEEDS_REVIEW'),
    ('nar_005', 'Phishing scam impersonating a $5000 emergency rebuild grant',            'inc_east_gippsland', 'GROWING',        'CORRECTION_PUBLISHED'),
    ('nar_006', 'Low-credibility speculation about understated Grampians wind change',    'inc_grampians',      'STEADY',         'DISMISSED'),
    ('nar_007', 'False water-bomber crash report in the Grampians',                       'inc_grampians',      'SPREADING_FAST', 'CONFIRMED_MISINFORMATION'),
    ('nar_008', 'Looting rumours in evacuated East Gippsland towns',                      'inc_east_gippsland', 'STEADY',         'NEEDS_REVIEW'),
    ('nar_009', 'Fake recovery donation account using fraudulent bank details',           'inc_east_gippsland', 'GROWING',        'CORRECTION_PUBLISHED');

INSERT INTO narrative_cluster_key_claims (narrative_cluster_id, content) VALUES
    ('nar_001', 'CFA has ordered a full evacuation of Bairnsdale CBD'),
    ('nar_001', 'The fire is closer to Bairnsdale than authorities are admitting'),
    ('nar_001', 'Residents are being kept in the dark about the true danger level'),

    ('nar_002', 'The Grampians fire was deliberately lit by arsonists'),
    ('nar_002', 'Fuel reduction burns were blocked by environmental groups'),
    ('nar_002', 'Authorities are covering up the true cause of the fire'),

    ('nar_003', 'Lakes Entrance Road (Princes Highway) is completely closed'),
    ('nar_003', 'There is no way to evacuate east from Bairnsdale'),
    ('nar_003', 'VicRoads is not updating road status accurately'),

    ('nar_004', 'A major wind change at 3pm will push the fire toward Apollo Bay'),
    ('nar_004', 'Bureau of Meteorology sources have confirmed the wind change privately'),

    ('nar_005', 'The Victorian Government is offering $5000 emergency rebuild grants'),
    ('nar_005', 'Residents must apply through a specific link to receive the grant'),
    ('nar_005', 'The application deadline is within 48 hours'),

    ('nar_006', 'A wind change will push the Grampians fire toward Halls Gap overnight'),
    ('nar_006', 'CFA is downplaying the severity of the wind change forecast'),

    -- Extras
    ('nar_007', 'A Coulson 737 water bomber crashed in the Grampians'),
    ('nar_007', 'Authorities are concealing the incident from the public'),

    ('nar_008', 'Looters have broken into evacuated homes in Mallacoota'),
    ('nar_008', 'Police are absent from evacuated towns'),

    ('nar_009', 'An official East Gippsland Recovery Fund is collecting donations via the BSB and account number provided'),
    ('nar_009', 'Donations should be transferred directly to the listed bank account');

-- ---------------------------------------------------------------------------
-- Matched facts
-- ---------------------------------------------------------------------------
INSERT INTO narrative_cluster_matched_facts (narrative_cluster_id, source, "timestamp", content) VALUES
    ('nar_001', 'CFA Official Bulletin', '2026-01-22T07:32:00+11:00',
     'No evacuation order has been issued for Bairnsdale CBD. Current status: Watch and Act for surrounding areas. Residents should monitor VicEmergency for updates.'),
    ('nar_001', 'VicEmergency',          '2026-01-22T07:15:00+11:00',
     'East Gippsland fire complex: fire is currently 4.2km from Bairnsdale township. All warnings are being issued in real time via VicEmergency app and website.'),

    ('nar_002', 'CFA Official Bulletin', '2026-01-21T20:00:00+11:00',
     'The cause of the Grampians National Park fire is under investigation. No evidence of deliberate ignition has been confirmed at this time.'),
    ('nar_002', 'DELWP',                 '2026-01-21T18:45:00+11:00',
     'Planned burn program for the Grampians region was conducted on schedule in autumn 2025. Details of completed burns are available on the DELWP website.'),

    ('nar_003', 'VicRoads',              '2026-01-22T12:30:00+11:00',
     'Princes Highway between Bairnsdale and Lakes Entrance is OPEN with reduced speed limits and CFA traffic management in place. Check traffic.vicroads.vic.gov.au for live updates.'),
    ('nar_003', 'VicEmergency',          '2026-01-22T12:15:00+11:00',
     'Eastbound evacuation routes from Bairnsdale remain accessible. Residents should follow directions from emergency services personnel on the ground.'),

    ('nar_004', 'Bureau of Meteorology', '2026-01-23T09:00:00+11:00',
     'A south-westerly wind change is forecast for the Otway Ranges region between 4pm and 6pm. Fire weather conditions will ease following the change. Official forecasts are available at bom.gov.au.'),

    ('nar_005', 'Victorian Government — Emergency Recovery', '2026-01-20T16:00:00+11:00',
     'The Victorian Government has not announced a $5000 emergency rebuild grant. All legitimate disaster recovery payments are administered through Services Australia and can be accessed at services.gov.au.'),
    ('nar_005', 'Scamwatch (ACCC)',      '2026-01-20T15:30:00+11:00',
     'Scamwatch has received reports of phishing links impersonating government disaster relief. Do not click links in unsolicited social media posts. Report suspicious activity at scamwatch.gov.au.'),

    ('nar_006', 'Bureau of Meteorology', '2026-01-21T21:00:00+11:00',
     'No significant wind change is forecast for the Grampians region overnight. Conditions expected to remain stable until mid-morning. Monitor bom.gov.au for official forecasts.'),
    ('nar_006', 'CFA Official Bulletin', '2026-01-21T21:30:00+11:00',
     'Grampians National Park fire: current containment lines are holding. No change to warning level for Halls Gap area at this time.'),

    ('nar_007', 'Coulson Aviation',      '2026-01-21T16:00:00+11:00',
     'All Coulson aircraft assigned to Victoria are accounted for. No incidents to report. Operations continuing as scheduled.'),
    ('nar_007', 'CFA Official Bulletin', '2026-01-21T16:10:00+11:00',
     'Reports circulating on social media of an air tanker crash in the Grampians are false. All crews are safe.'),

    ('nar_008', 'Victoria Police',       '2026-01-22T22:30:00+11:00',
     'Police patrols have been increased in evacuated areas of East Gippsland. Two unconfirmed reports of property interference are under investigation. No widespread looting has been reported.'),

    ('nar_009', 'Bushfire Recovery Victoria', '2026-01-21T13:00:00+11:00',
     'The official recovery donation channel is the Victorian Bushfire Appeal hosted by the Bendigo Bank Community Enterprise Foundation. Verify any account before donating.'),
    ('nar_009', 'Scamwatch (ACCC)',      '2026-01-21T13:30:00+11:00',
     'Reports of fraudulent bushfire donation accounts. Verify legitimacy before transferring funds; report to scamwatch.gov.au.');

INSERT INTO narrative_cluster_posts (cluster_id, post_id) VALUES
    ('nar_001', 'post_001'), ('nar_001', 'post_002'), ('nar_001', 'post_003'),
    ('nar_002', 'post_004'), ('nar_002', 'post_005'),
    ('nar_003', 'post_006'), ('nar_003', 'post_007'),
    ('nar_004', 'post_008'), ('nar_004', 'post_009'),
    ('nar_005', 'post_010'), ('nar_005', 'post_011'), ('nar_005', 'post_012'),
    ('nar_006', 'post_013'), ('nar_006', 'post_014'),
    ('nar_007', 'post_015'), ('nar_007', 'post_016'),
    ('nar_008', 'post_017'), ('nar_008', 'post_018'),
    ('nar_009', 'post_019'), ('nar_009', 'post_020');

COMMIT;
