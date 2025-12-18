/**
 * This is the default configuration file for the Superdesk application. By default,
 * the app will use the file with the name "superdesk.config.js" found in the current
 * working directory, but other files may also be specified using relative paths with
 * the SUPERDESK_CONFIG environment variable or the grunt --config flag.
 */
module.exports = function() {
    return {
        apps: [
            'superdesk.analytics',
            'superdesk-planning',
            'superdesk-publisher'
        ],
        importApps: [
            '../index',
            'superdesk-planning',
            'superdesk-analytics',
            'superdesk-publisher'
        ],

        defaultRoute: '/workspace/monitoring',

         publisher: {
            protocol: 'https',                /* http or https */
            tenant: '',              /* tenant - semantically subdomain, '' is allowed */
            domain: '',           /* domain name for the publisher */
            base: 'api/v2',                  /* api base path */

            wsProtocol: 'wss',                /* ws or wss (websocket); if unspecified or '' defaults to 'wss' */
            wsDomain: '',  /* domain name (usually domain as above) */
                                            /* e.g.: example.com, abc.example.com */
                                            /* tenant, as above, is NOT used for websocket */
            wsPath: '/ws',                    /* path to websocket root dir */
            wsPort: '80',                   /* if not specified: defaults to 443 for wss, 80 for ws */
            hideContentRoutesInPublishPane: false, /* hides routes of type "content" from select box in publish panes in monitoring view as well as in output control. If not specified: defaults to false */
            hideCustomRoutesInPublishPane: false   /* hides routes of type "custom" from select box in publish panes in monitoring view as well as in output control. If not specified: defaults to false */
        },

        langOverride: {
            en: {
                'ANPA Category': 'Category',
                'ANPA CATEGORY': 'CATEGORY'
            }
        },

        view: {
            timeformat: 'HH:mm',
            dateformat: 'YYYY-MM-DD',
        },

        shortTimeFormat: 'HH:mm, YYYY-MM-DD',
        shortDateFormat: 'HH:mm, YYYY-MM-DD',
        shortWeekFormat: 'HH:mm, YYYY-MM-DD',
        startingDay: '1',

        defaultTimezone: 'Europe/Prague',

        editor3: { browserSpellCheck: true, },

        search_cvs: [
            {id: 'topics', name:'Topics', field: 'subject', list: 'topics'},
            {id: 'language', name:'Language', field: 'language', list: 'languages'},
            {id: 'project', name:'Project', field: 'project', list: 'project'}
            {id: 'claimformat', name:'Claim format', field: 'claim_format', list: 'claimformat'},
            {id: 'claimtopic', name:'Claim topic', field: 'claim_topic', list: 'claimtopic'},
            {id: 'claimtype', name:'Claim type', field: 'claim_type', list: 'claimtype'},
            {id: 'countrymention1', name:'Primary country', field: 'primary_country', list: 'countrymention1'},
            {id: 'countrymention2nd', name:'2nd country mention', field: 'country_mention_2', list: 'countrymention2nd'},
            {id: 'countrymention3rd', name:'3rd country mention', field: 'country_mention_3', list: 'countrymention3rd'},
            {id: 'countrymention4th', name:'4th country mention', field: 'country_mention_4', list: 'countrymention4th'},
            {id: 'countrymention5th', name:'5th country mention', field: 'country_mention_5', list: 'countrymention5th'},
            {id: 'countriesmention', name:'Countries mentioned', field: 'countries_mentioned', list: 'countriesmention'},
            {id: 'debunklanguage', name:'Debunk language', field: 'debunk_language', list: 'debunklanguage'},
            {id: 'debunkrating', name:'Debunk rating', field: 'debunk_rating', list: 'debunkrating'},
            {id: 'geccategory', name:'GEC category', field: 'gec_category', list: 'geccategory'},
            {id: 'harmtype', name:'Harm type', field: 'harm_type', list: 'harmtype'},
            {id: 'primaryplatform', name:'Primary platform', field: 'primary_platform', list: 'primaryplatform'},
        ],

        features: {
            preview: 1,
            swimlane: {columnsLimit: 99},
            swimlane: {defaultNumberOfColumns: 4},
            editor3: true,
            editorHighlights: true,
            noPublishOnAuthoringDesk: true,
            customAuthoringTopbar: {
                toDesk: true,
                publish: true,
            },
            validatePointOfInterestForImages: true,
            editorHighlights: true,
            editFeaturedImage: true,
            searchShortcut: true,
            elasticHighlight: true,
            planning: true,
            autorefreshContent: true,
            nestedItemsInOutputStage: true,
            planning: true,
            customAuthoringTopbar: {
                toDesk: true,
            },
        },

        item_profile: { change_profile: 1 },

        workspace: {
            planning: true,
            assignments: true,
            analytics: true,
        },

        ui: {
            italicAbstract: false,
            },

        list: {
            priority: [
                'priority',
                'urgency'
            ],
            firstLine: [
                'headline',
                'highlights',
                'markedDesks',
                'associatedItems',
                'versioncreated'
            ],
            secondLine: [
                'language',
                'state',
                'update',
                'scheduledDateTime',
                'flags',
                'updated',
                'provider',
                'desk',
                'fetchedDesk',
                'used',
                'nestedlink',
                'translations'
            ]
        },

        monitoring: {
            scheduled: {
                sort: {
                    default: { field: 'publish_schedule', order: 'asc' },
                    allowed_fields_to_sort: [ 'publish_schedule' ]
                }
            },
        },
    };
};
