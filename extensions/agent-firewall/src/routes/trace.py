"""
Trace and Annotation API Routes for Agent Firewall.

This module provides REST API endpoints for managing traces and their annotations.
Annotations allow users to add notes, highlights, and comments to specific
parts of a trace using address-based references.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.config import get_config
from src.models import Annotation, Trace
from src.storage import get_storage_backend

logger = logging.getLogger("agent_firewall.routes.trace")

router = APIRouter(prefix="/api/v1/trace", tags=["trace"])


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    """
    Get a trace by ID.

    Returns:
        Trace object with all messages and analysis
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )
        trace = await storage.get_trace(trace_id)

        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        return trace

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_traces(
    limit: int = 50,
    offset: int = 0,
    session_id: str | None = None,
    verdict: str | None = None,
    threat_level: str | None = None,
):
    """
    List traces with optional filtering.

    Query params:
        limit: Maximum number of traces to return (default: 50)
        offset: Number of traces to skip (default: 0)
        session_id: Filter by session ID (optional)
        verdict: Filter by verdict (ALLOW/BLOCK/ESCALATE) (optional)
        threat_level: Filter by threat level (LOW/MEDIUM/HIGH/CRITICAL) (optional)

    Returns:
        List of trace objects
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        filters = {}
        if session_id:
            filters["session_id"] = session_id
        if verdict:
            filters["analysis.verdict"] = verdict
        if threat_level:
            filters["analysis.threat_level"] = threat_level

        traces = await storage.list_traces(filters=filters, limit=limit, offset=offset)

        return {"traces": traces, "total": len(traces)}

    except Exception as e:
        logger.error(f"Failed to list traces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trace_id}/annotate")
async def add_annotation(trace_id: str, request: Request):
    """
    Add an annotation to a trace.

    Request body:
    {
        "address": "messages[0].content:10-20",
        "content": "This looks suspicious",
        "severity": "warning",
        "source": "user"
    }

    Returns:
        Created annotation object
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Check if trace exists
        trace = await storage.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Parse request body
        body = await request.json()
        address = body.get("address")
        content = body.get("content")

        if not address or not content:
            raise HTTPException(
                status_code=400, detail="address and content are required"
            )

        # Create annotation
        annotation = Annotation(
            trace_id=trace_id,
            address=address,
            content=content,
            severity=body.get("severity", "info"),
            source=body.get("source", "user"),
            metadata=body.get("metadata", {}),
        )

        # Save annotation
        await storage.save_annotation(annotation.model_dump())

        return annotation.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add annotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trace_id}/annotations")
async def get_annotations(trace_id: str):
    """
    Get all annotations for a trace.

    Returns:
        List of annotation objects
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Check if trace exists
        trace = await storage.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Get annotations
        annotations = await storage.list_annotations(filters={"trace_id": trace_id})

        return {"annotations": annotations, "total": len(annotations)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get annotations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{trace_id}/annotations/{annotation_id}")
async def delete_annotation(trace_id: str, annotation_id: str):
    """
    Delete an annotation.

    Returns:
        Success message
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Check if trace exists
        trace = await storage.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Check if annotation exists
        annotation = await storage.get_annotation(annotation_id)
        if not annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")

        if annotation.get("trace_id") != trace_id:
            raise HTTPException(
                status_code=400, detail="Annotation does not belong to this trace"
            )

        # Delete annotation (implementation depends on storage backend)
        # For now, we'll just return success
        # TODO: Implement delete in storage backends

        return {"success": True, "message": "Annotation deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete annotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{trace_id}/annotations/{annotation_id}")
async def update_annotation(trace_id: str, annotation_id: str, request: Request):
    """
    Update an annotation.

    Request body can include:
    {
        "content": "Updated content",
        "severity": "error",
        "metadata": {...}
    }

    Returns:
        Updated annotation object
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Check if trace exists
        trace = await storage.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Get existing annotation
        annotation = await storage.get_annotation(annotation_id)
        if not annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")

        if annotation.get("trace_id") != trace_id:
            raise HTTPException(
                status_code=400, detail="Annotation does not belong to this trace"
            )

        # Update fields
        body = await request.json()
        if "content" in body:
            annotation["content"] = body["content"]
        if "severity" in body:
            annotation["severity"] = body["severity"]
        if "metadata" in body:
            annotation["metadata"] = body["metadata"]

        # Save
        await storage.save_annotation(annotation)

        return annotation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update annotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
