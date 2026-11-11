# Problem Statement

## Background

The corporation currently relies on scattered spreadsheets to record safety information for its nuclear power plants. Plant details, reactor unit inventories, and operating readings are difficult to keep consistent across files. This makes it harder for staff to find a complete record, spot missing relationships, and remove outdated data without leaving orphaned entries behind.

The project replaces that workflow with a small relational database application and a dashboard for entering, reviewing, and deleting records.

## Core Problem

The information has three related levels:

1. **Plants** identify each station and store the safety officer's contact email.
2. **Reactor units** belong to a plant and store a unit identifier and commissioning date.
3. **Safety readings** belong to a reactor unit and store a reading type and measured value.

Spreadsheet rows do not reliably enforce these relationships. A plant can be removed while related unit data remains, a unit can be separated from its readings, and different versions of a name or identifier can make related records difficult to reconcile. The replacement must make these relationships explicit and preserve them automatically.

## Project Goal

Build a single Python application backed by SQLite that lets a user record and review plant, reactor unit, and safety reading data through a clear graphical interface. The application should work in a desktop development environment and offer a notebook-compatible interface for Jupyter or Google Colab.

## Required Data Integrity

- Plant names must be unique, and each plant must have a safety officer contact email.
- Every reactor unit must reference an existing plant.
- Every safety reading must reference an existing reactor unit.
- Deleting a plant must cascade to its reactor units and all readings under those units.
- Deleting a reactor unit must cascade to its readings.
- Deleting an individual reading must leave its unit and plant intact.
- Measured values must be numeric and non-negative; required text fields must not be blank.

## User Workflow

The dashboard should let users submit a plant name, officer email, unit identifier, commissioning date, reading type, and measured value together. If the plant already exists, the application should reuse its database ID; otherwise, it should create the plant before adding the unit and reading.

Users should also be able to choose a plant, reactor unit, or safety reading from current database records and delete it. After an add or delete operation, the form state, delete selectors, and displayed data should refresh immediately so they reflect the database's current state.

## Review and Reporting Views

The interface should provide a combined view joining plant, reactor unit, and safety reading data, along with separate views of each underlying table. This gives users both a readable end-to-end record and access to the stored relational rows.

## Runtime and Initialization

The application should initialize its SQLite schema automatically, enable foreign-key enforcement, and insert sample entries only when all three tables are empty. The same source file should detect notebook use and select an interface that avoids opening a desktop window inside notebook environments.

## Intended Outcome

The result is a more dependable and reviewable safety logging workflow: records remain linked to their owners, parent deletions clean up dependent data, individual readings can be removed without damaging parent records, and users can inspect the current dataset from one dashboard.
