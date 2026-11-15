//! Small, safe API errors for future Actix applications.
//!
//! This maps explicitly returned [`ApiError`] values. It does not normalize
//! Actix extractor errors, default routes, authentication or application logs.

#![forbid(unsafe_code)]

use std::fmt;

use actix_web::{HttpResponse, ResponseError, http::StatusCode, http::header::CACHE_CONTROL};
use serde::Serialize;
use uuid::Uuid;

/// Stable machine-readable classifications, independent of application rules.
#[cfg_attr(feature = "openapi", derive(utoipa::ToSchema))]
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    ValidationFailed,
    Unauthenticated,
    Forbidden,
    NotFound,
    MethodNotAllowed,
    Conflict,
    InternalError,
}

impl ErrorCode {
    fn status(self) -> StatusCode {
        match self {
            Self::ValidationFailed => StatusCode::UNPROCESSABLE_ENTITY,
            Self::Unauthenticated => StatusCode::UNAUTHORIZED,
            Self::Forbidden => StatusCode::FORBIDDEN,
            Self::NotFound => StatusCode::NOT_FOUND,
            Self::MethodNotAllowed => StatusCode::METHOD_NOT_ALLOWED,
            Self::Conflict => StatusCode::CONFLICT,
            Self::InternalError => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    fn message(self) -> &'static str {
        match self {
            Self::ValidationFailed => "Some fields are invalid.",
            Self::Unauthenticated => "Authentication is required.",
            Self::Forbidden => "You do not have permission to perform this action.",
            Self::NotFound => "The requested resource was not found.",
            Self::MethodNotAllowed => "This request method is not allowed.",
            Self::Conflict => "The resource changed. Refresh and try again.",
            Self::InternalError => "An unexpected error occurred.",
        }
    }
}

/// Only fixed field-error messages are published; input values are never held.
#[cfg_attr(feature = "openapi", derive(utoipa::ToSchema))]
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FieldErrorCode {
    Required,
    Invalid,
    OutOfRange,
}

impl FieldErrorCode {
    fn message(self) -> &'static str {
        match self {
            Self::Required => "This field is required.",
            Self::Invalid => "This field is invalid.",
            Self::OutOfRange => "This field is out of range.",
        }
    }
}

/// A developer-defined schema field path and a safe validation classification.
///
/// Paths are static ASCII identifiers separated by dots, at most 128 bytes.
/// Each segment starts with a letter or underscore and continues with letters,
/// digits or underscores. Use schema paths, not submitted keys, IDs or values.
/// Array indices and bracket notation are intentionally unsupported.
#[cfg_attr(feature = "openapi", derive(utoipa::ToSchema))]
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct FieldError {
    field: &'static str,
    code: FieldErrorCode,
    message: &'static str,
}

impl FieldError {
    pub fn new(field: &'static str, code: FieldErrorCode) -> Result<Self, InvalidFieldPath> {
        let valid = !field.is_empty()
            && field.len() <= 128
            && field.split('.').all(|segment| {
                let mut bytes = segment.bytes();
                bytes
                    .next()
                    .is_some_and(|first| first.is_ascii_alphabetic() || first == b'_')
                    && bytes.all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
            });
        if !valid {
            return Err(InvalidFieldPath);
        }
        Ok(Self {
            field,
            code,
            message: code.message(),
        })
    }
}

/// Invalid metadata is rejected without retaining or formatting the path.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidFieldPath;

impl fmt::Display for InvalidFieldPath {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("Invalid schema field path")
    }
}

impl std::error::Error for InvalidFieldPath {}

#[cfg_attr(feature = "openapi", derive(utoipa::ToSchema))]
#[derive(Debug, Serialize)]
pub struct ErrorEnvelope {
    pub error: ErrorBody,
}

#[cfg_attr(feature = "openapi", derive(utoipa::ToSchema))]
#[derive(Debug, Serialize)]
pub struct ErrorBody {
    code: ErrorCode,
    message: &'static str,
    error_id: Uuid,
    field_errors: Vec<FieldError>,
}

/// An explicitly returned error with a server-generated, stable UUIDv4.
///
/// Construction never accepts public message text, request IDs or debug details.
/// Application diagnostics belong in separately reviewed, redacted telemetry.
#[derive(Debug)]
pub struct ApiError {
    envelope: ErrorEnvelope,
}

impl ApiError {
    fn new(code: ErrorCode, field_errors: Vec<FieldError>) -> Self {
        Self {
            envelope: ErrorEnvelope {
                error: ErrorBody {
                    code,
                    message: code.message(),
                    error_id: Uuid::new_v4(),
                    field_errors,
                },
            },
        }
    }

    pub fn validation(field_errors: Vec<FieldError>) -> Self {
        Self::new(ErrorCode::ValidationFailed, field_errors)
    }

    pub fn unauthenticated() -> Self {
        Self::new(ErrorCode::Unauthenticated, Vec::new())
    }

    pub fn forbidden() -> Self {
        Self::new(ErrorCode::Forbidden, Vec::new())
    }

    pub fn not_found() -> Self {
        Self::new(ErrorCode::NotFound, Vec::new())
    }

    pub fn method_not_allowed() -> Self {
        Self::new(ErrorCode::MethodNotAllowed, Vec::new())
    }

    pub fn conflict() -> Self {
        Self::new(ErrorCode::Conflict, Vec::new())
    }

    pub fn internal() -> Self {
        Self::new(ErrorCode::InternalError, Vec::new())
    }

    /// Consume an internal cause without exposing it through responses or errors.
    pub fn internal_from(_cause: impl std::error::Error) -> Self {
        Self::internal()
    }

    pub fn code(&self) -> ErrorCode {
        self.envelope.error.code
    }

    pub fn error_id(&self) -> Uuid {
        self.envelope.error.error_id
    }
}

impl fmt::Display for ApiError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "{} (error {})",
            self.envelope.error.message,
            self.error_id()
        )
    }
}

impl std::error::Error for ApiError {}

impl ResponseError for ApiError {
    fn status_code(&self) -> StatusCode {
        self.code().status()
    }

    fn error_response(&self) -> HttpResponse {
        HttpResponse::build(self.status_code())
            .insert_header((CACHE_CONTROL, "no-store"))
            .json(&self.envelope)
    }
}
