"""Kubernetes apiVersion/kind pairs removed at a given release.

Source: the Kubernetes deprecated API migration guide
(https://kubernetes.io/docs/reference/using-api/deprecation-guide/). Only
pairs actually removed (not merely deprecated) are listed, each tagged with
the first release that no longer serves it.
"""

REMOVED_APIS = {
    ("extensions/v1beta1", "Ingress"): "1.22",
    ("networking.k8s.io/v1beta1", "Ingress"): "1.22",
    ("networking.k8s.io/v1beta1", "IngressClass"): "1.22",
    ("rbac.authorization.k8s.io/v1beta1", "Role"): "1.22",
    ("rbac.authorization.k8s.io/v1beta1", "RoleBinding"): "1.22",
    ("rbac.authorization.k8s.io/v1beta1", "ClusterRole"): "1.22",
    ("rbac.authorization.k8s.io/v1beta1", "ClusterRoleBinding"): "1.22",
    ("scheduling.k8s.io/v1beta1", "PriorityClass"): "1.22",
    ("apiextensions.k8s.io/v1beta1", "CustomResourceDefinition"): "1.22",
    ("admissionregistration.k8s.io/v1beta1", "ValidatingWebhookConfiguration"): "1.22",
    ("admissionregistration.k8s.io/v1beta1", "MutatingWebhookConfiguration"): "1.22",
    ("coordination.k8s.io/v1beta1", "Lease"): "1.22",
    ("certificates.k8s.io/v1beta1", "CertificateSigningRequest"): "1.22",
    ("storage.k8s.io/v1beta1", "StorageClass"): "1.22",
    ("storage.k8s.io/v1beta1", "CSIDriver"): "1.22",
    ("storage.k8s.io/v1beta1", "CSINode"): "1.22",
    ("storage.k8s.io/v1beta1", "VolumeAttachment"): "1.22",
    ("apiregistration.k8s.io/v1beta1", "APIService"): "1.22",
    ("batch/v1beta1", "CronJob"): "1.25",
    ("policy/v1beta1", "PodDisruptionBudget"): "1.25",
    ("policy/v1beta1", "PodSecurityPolicy"): "1.25",
    ("discovery.k8s.io/v1beta1", "EndpointSlice"): "1.25",
    ("events.k8s.io/v1beta1", "Event"): "1.25",
    ("autoscaling/v2beta1", "HorizontalPodAutoscaler"): "1.25",
    ("autoscaling/v2beta2", "HorizontalPodAutoscaler"): "1.26",
    ("storage.k8s.io/v1beta1", "CSIStorageCapacity"): "1.27",
    ("flowcontrol.apiserver.k8s.io/v1beta1", "FlowSchema"): "1.29",
    ("flowcontrol.apiserver.k8s.io/v1beta2", "FlowSchema"): "1.29",
    ("flowcontrol.apiserver.k8s.io/v1beta1", "PriorityLevelConfiguration"): "1.29",
    ("flowcontrol.apiserver.k8s.io/v1beta2", "PriorityLevelConfiguration"): "1.29",
}


def version_tuple(v):
    return tuple(int(p) for p in v.split("."))


def removed_at_or_before(api_version, kind, target_version):
    """Return the removal version if (api_version, kind) is gone by target_version, else None."""
    removed_in = REMOVED_APIS.get((api_version, kind))
    if removed_in is None:
        return None
    if version_tuple(removed_in) <= version_tuple(target_version):
        return removed_in
    return None
