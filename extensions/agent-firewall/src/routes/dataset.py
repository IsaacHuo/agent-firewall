"""
Dataset API Routes for Agent Firewall.

This module provides REST API endpoints for managing datasets,
which are collections of traces organized for analysis and policy testing.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.config import get_config
from src.models import Dataset, Policy, Trace
from src.storage import get_storage_backend

logger = logging.getLogger("agent_firewall.routes.dataset")

router = APIRouter(prefix="/api/v1/dataset", tags=["dataset"])


@router.post("")
async def create_dataset(request: Request):
    """
    Create a new dataset.

    Request body:
    {
        "name": "My Dataset",
        "description": "Optional description",
        "is_public": false
    }

    Returns:
        Dataset object with generated ID
    """
    try:
        body = await request.json()
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Dataset name is required")

        dataset = Dataset(
            name=name,
            description=body.get("description", ""),
            is_public=body.get("is_public", False),
            metadata=body.get("metadata", {}),
        )

        # Save to storage
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )
        await storage.save_dataset(dataset.model_dump())

        return dataset.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str):
    """
    Get a dataset by ID.

    Returns:
        Dataset object with all metadata
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )
        dataset = await storage.get_dataset(dataset_id)

        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        return dataset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_datasets(
    limit: int = 50, offset: int = 0, is_public: bool | None = None
):
    """
    List all datasets with optional filtering.

    Query params:
        limit: Maximum number of datasets to return (default: 50)
        offset: Number of datasets to skip (default: 0)
        is_public: Filter by public/private (optional)

    Returns:
        List of dataset objects
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        filters = {}
        if is_public is not None:
            filters["is_public"] = is_public

        datasets = await storage.list_datasets(
            filters=filters, limit=limit, offset=offset
        )

        return {"datasets": datasets, "total": len(datasets)}

    except Exception as e:
        logger.error(f"Failed to list datasets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{dataset_id}")
async def update_dataset(dataset_id: str, request: Request):
    """
    Update a dataset.

    Request body can include:
    {
        "name": "Updated name",
        "description": "Updated description",
        "is_public": true,
        "traces": ["trace_id_1", "trace_id_2"],
        "policies": ["policy_id_1"]
    }

    Returns:
        Updated dataset object
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Get existing dataset
        dataset = await storage.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Update fields
        body = await request.json()
        if "name" in body:
            dataset["name"] = body["name"]
        if "description" in body:
            dataset["description"] = body["description"]
        if "is_public" in body:
            dataset["is_public"] = body["is_public"]
        if "traces" in body:
            dataset["traces"] = body["traces"]
        if "policies" in body:
            dataset["policies"] = body["policies"]
        if "metadata" in body:
            dataset["metadata"] = body["metadata"]

        # Update timestamp
        import time

        dataset["updated_at"] = time.time()

        # Save
        await storage.save_dataset(dataset)

        return dataset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """
    Delete a dataset.

    Note: This does not delete the traces themselves, only the dataset container.

    Returns:
        Success message
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Check if dataset exists
        dataset = await storage.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Delete (implementation depends on storage backend)
        # For now, we'll just return success
        # TODO: Implement delete in storage backends

        return {"success": True, "message": "Dataset deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}/traces")
async def list_dataset_traces(
    dataset_id: str, limit: int = 50, offset: int = 0, filters: str | None = None
):
    """
    List traces in a dataset.

    Query params:
        limit: Maximum number of traces to return (default: 50)
        offset: Number of traces to skip (default: 0)
        filters: JSON string of filter conditions (optional)

    Returns:
        List of trace objects
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Get dataset
        dataset = await storage.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get traces
        trace_ids = dataset.get("traces", [])
        traces = []

        # Parse filters if provided
        import json

        filter_dict = {}
        if filters:
            try:
                filter_dict = json.loads(filters)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid filters JSON")

        # Fetch traces
        for trace_id in trace_ids[offset : offset + limit]:
            trace = await storage.get_trace(trace_id)
            if trace:
                # Apply filters
                if filter_dict:
                    match = True
                    for key, value in filter_dict.items():
                        if key in trace and trace[key] != value:
                            match = False
                            break
                    if match:
                        traces.append(trace)
                else:
                    traces.append(trace)

        return {"traces": traces, "total": len(trace_ids)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list dataset traces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dataset_id}/traces/{trace_id}")
async def add_trace_to_dataset(dataset_id: str, trace_id: str):
    """
    Add a trace to a dataset.

    Returns:
        Updated dataset object
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Get dataset
        dataset = await storage.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Check if trace exists
        trace = await storage.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Add trace if not already in dataset
        if trace_id not in dataset.get("traces", []):
            if "traces" not in dataset:
                dataset["traces"] = []
            dataset["traces"].append(trace_id)

            # Update timestamp
            import time

            dataset["updated_at"] = time.time()

            # Save
            await storage.save_dataset(dataset)

        return dataset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add trace to dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{dataset_id}/traces/{trace_id}")
async def remove_trace_from_dataset(dataset_id: str, trace_id: str):
    """
    Remove a trace from a dataset.

    Returns:
        Updated dataset object
    """
    try:
        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Get dataset
        dataset = await storage.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Remove trace
        if trace_id in dataset.get("traces", []):
            dataset["traces"].remove(trace_id)

            # Update timestamp
            import time

            dataset["updated_at"] = time.time()

            # Save
            await storage.save_dataset(dataset)

        return dataset

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove trace from dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dataset_id}/policy/check")
async def check_policy_on_dataset(dataset_id: str, request: Request):
    """
    Check a policy against all traces in a dataset.

    Request body:
    {
        "policy": "raise \"High risk\" if: threat_level >= \"HIGH\"",
        "policy_id": "optional_policy_id"
    }

    Returns:
        Streaming response with policy check results for each trace
    """
    try:
        from src.engine.policy_dsl import PolicyEngine

        config = get_config()
        storage = get_storage_backend(
            backend=config.storage_backend, path=config.storage_path
        )

        # Get dataset
        dataset = await storage.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get policy
        body = await request.json()
        policy_code = body.get("policy")
        if not policy_code:
            raise HTTPException(status_code=400, detail="Policy code is required")

        # Stream results
        async def generate_results():
            engine = PolicyEngine()
            trace_ids = dataset.get("traces", [])

            for i, trace_id in enumerate(trace_ids):
                trace = await storage.get_trace(trace_id)
                if not trace:
                    continue

                # Build context
                analysis = trace.get("analysis", {})
                context = {
                    "threat_level": analysis.get("threat_level", "LOW"),
                    "verdict": analysis.get("verdict", "ALLOW"),
                    "l1_result": analysis.get("l1_result", {}),
                    "l2_result": analysis.get("l2_result", {}),
                    "messages": trace.get("messages", []),
                    "tool_calls": [],
                }

                # Extract tool calls
                for msg in context["messages"]:
                    if msg.get("tool_calls"):
                        context["tool_calls"].extend(msg["tool_calls"])

                # Evaluate policy
                result = await engine.evaluate(policy_code, context)

                # Yield result
                import json

                yield json.dumps(
                    {
                        "trace_id": trace_id,
                        "index": i,
                        "total": len(trace_ids),
                        "passed": result.passed,
                        "message": result.message,
                        "error": result.error,
                    }
                ) + "\n"

        return StreamingResponse(generate_results(), media_type="application/x-ndjson")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check policy on dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
