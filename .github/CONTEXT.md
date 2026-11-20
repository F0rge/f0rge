# Delivery

How a change merged to `main` is built, tested and put in front of users. It exists so that "what runs, and what ends up where?" has one vocabulary.

## Language

**Project**:
One unit in the Nx workspace: an app's backend, an app's frontend, or a shared library.
_Avoid_: Component, package, module

**App**:
A product that is released as a whole, made of one or more Projects that share a scope.
_Avoid_: Service, system, component

**Host**:
The place an App runs: the Pi or Railway. An App has exactly one Host.
_Avoid_: Target, environment, platform, destination

**Artifact**:
The container image built from one Project at one commit.
_Avoid_: Build, bundle, package

**Release**:
All of one App's Artifacts from a single commit going live on its Host.
_Avoid_: Deploy (as a noun), rollout, promotion, publication
