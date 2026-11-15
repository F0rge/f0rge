export interface paths {
    "/api/v1/listings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listings"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["state"];
        put: operations["update_state"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/state/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["import"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/state/import-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["preview"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["status"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["health"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["ready"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Alert: {
            comparables: number;
            confidence: string;
            country: string;
            /** Format: double */
            estimated_profit: number;
            id: string;
            /** Format: double */
            model_median_days?: number | null;
            /** Format: double */
            model_sell_through?: number | null;
            name: string;
            /** Format: double */
            price: number;
            reason: string;
            /** Format: double */
            reference_price: number;
            risk_flags: string[];
            /** Format: double */
            roi_percent: number;
            url: string;
        };
        BrowserState: {
            bikes?: components["schemas"]["CategoryState"];
            /** Format: int32 */
            version?: number;
            wheels?: components["schemas"]["CategoryState"];
        } & {
            [key: string]: unknown;
        };
        CategoryState: {
            costs?: {
                [key: string]: number;
            };
            log?: components["schemas"]["Trade"][];
            watch?: {
                [key: string]: components["schemas"]["WatchEntry"];
            };
        } & {
            [key: string]: unknown;
        };
        ErrorBody: {
            code: components["schemas"]["ErrorCode"];
            /** Format: uuid */
            error_id: string;
            field_errors: components["schemas"]["FieldError"][];
            message: string;
        };
        /**
         * @description Stable machine-readable classifications, independent of application rules.
         * @enum {string}
         */
        ErrorCode: "validation_failed" | "unauthenticated" | "forbidden" | "not_found" | "method_not_allowed" | "conflict" | "internal_error";
        ErrorEnvelope: {
            error: components["schemas"]["ErrorBody"];
        };
        /**
         * @description A developer-defined schema field path and a safe validation classification.
         *
         *     Paths are static ASCII identifiers separated by dots, at most 128 bytes.
         *     Each segment starts with a letter or underscore and continues with letters,
         *     digits or underscores. Use schema paths, not submitted keys, IDs or values.
         *     Array indices and bracket notation are intentionally unsupported.
         */
        FieldError: {
            code: components["schemas"]["FieldErrorCode"];
            field: string;
            message: string;
        };
        /**
         * @description Only fixed field-error messages are published; input values are never held.
         * @enum {string}
         */
        FieldErrorCode: "required" | "invalid" | "out_of_range";
        Health: {
            source_commit: string;
            status: string;
            version: string;
        };
        Identity: {
            subject: string;
        };
        ImportCounts: {
            costs: number;
            trades: number;
            watches: number;
        };
        ImportPreview: {
            counts: components["schemas"]["ImportCounts"];
            /** Format: int64 */
            expected_revision: number;
            warnings: string[];
        };
        ImportWrite: {
            /** Format: int64 */
            expected_revision: number;
            source: unknown;
            state: components["schemas"]["BrowserState"];
        };
        /** @enum {string} */
        Kind: "bikes" | "wheels";
        Listing: {
            /** Format: double */
            average_ask?: number | null;
            brake: string;
            brand: string;
            comparables: number;
            confidence: string;
            country: string;
            /** Format: double */
            cut_per_day?: number | null;
            /** Format: double */
            days_listed: number;
            /** Format: int64 */
            description_length: number;
            /** Format: double */
            discount_percent?: number | null;
            /** Format: double */
            dispersion?: number | null;
            /** Format: double */
            distance_km?: number | null;
            first_seen: string;
            gone_at?: string | null;
            history: components["schemas"]["PricePoint"][];
            id: string;
            kind: components["schemas"]["Kind"];
            model: string;
            name: string;
            next_up?: components["schemas"]["NextUp"] | null;
            /** Format: double */
            original_price: number;
            /** Format: int64 */
            photo_count: number;
            /** Format: double */
            price: number;
            /** Format: double */
            price_drop_percent?: number | null;
            price_reduced: boolean;
            /** Format: double */
            reference_price?: number | null;
            rim_material: string;
            risk_flags: string[];
            /** Format: int64 */
            seller_reviews?: number | null;
            size?: string | null;
            /** Format: double */
            sold_percent?: number | null;
            sold_sample?: number | null;
            url: string;
            /** Format: double */
            versus_typical?: number | null;
            wheel_system: string;
            /** Format: int32 */
            year?: number | null;
            /** Format: double */
            z_score?: number | null;
        };
        ListingsResponse: {
            active: number;
            alerts: components["schemas"]["Alert"][];
            generated: string;
            gone: number;
            items: components["schemas"]["Listing"][];
            kind: components["schemas"]["Kind"];
            models: components["schemas"]["ModelMarket"][];
            quarantined: components["schemas"]["QuarantinedListing"][];
            today: string;
        };
        ModelMarket: {
            active: number;
            disappeared: components["schemas"]["PricePoint"][];
            gone30: number;
            /** Format: double */
            median_days?: number | null;
            name: string;
            /** Format: double */
            sell_through?: number | null;
            trend: components["schemas"]["ModelTrend"][];
        };
        ModelTrend: {
            day: string;
            /** Format: double */
            median_price: number;
            n: number;
        };
        NextUp: {
            age_lower_bound: boolean;
            /** Format: int64 */
            days_listed?: number | null;
            /** Format: double */
            price: number;
            ties: number;
            url: string;
        };
        PricePoint: {
            day: string;
            /** Format: double */
            price: number;
        };
        QuarantinedListing: {
            id: string;
            reason: string;
        };
        StateResponse: {
            /** Format: int64 */
            revision: number;
            state: components["schemas"]["BrowserState"];
        };
        StateWrite: {
            /** Format: int64 */
            expected_revision: number;
            state: components["schemas"]["BrowserState"];
        };
        StatusResponse: {
            blocked: boolean;
            /** Format: int32 */
            detail_attempts: number;
            /** Format: int32 */
            detail_limit: number;
            identity: components["schemas"]["Identity"];
            last_success?: string | null;
            stale: boolean;
            status: string;
            version: string;
        };
        Trade: {
            bd: string;
            /** Format: double */
            buy: number;
            id?: string | null;
            name: string;
            sd?: string | null;
            /** Format: double */
            sell?: number | null;
            url: string;
        } & {
            [key: string]: unknown;
        };
        WatchEntry: {
            n: string;
            /** Format: double */
            p: number;
            t: string;
            u: string;
        } & {
            [key: string]: unknown;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listings: {
        parameters: {
            query: {
                kind: components["schemas"]["Kind"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ListingsResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    state: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StateResponse"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    update_state: {
        parameters: {
            query?: never;
            header: {
                /** @description Subject captured with the browser draft; must match verified identity */
                "X-Buycycle-Expected-Identity": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StateWrite"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StateResponse"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    import: {
        parameters: {
            query?: never;
            header: {
                /** @description Subject captured with the browser draft; must match verified identity */
                "X-Buycycle-Expected-Identity": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportWrite"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StateResponse"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    preview: {
        parameters: {
            query?: never;
            header: {
                /** @description Subject captured with the browser draft; must match verified identity */
                "X-Buycycle-Expected-Identity": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportWrite"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportPreview"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    status: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatusResponse"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    health: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    ready: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
}
