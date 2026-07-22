"""
Clinical report generation service
Generates structured clinical reports from predictions
"""

from typing import Dict, List

from src.core.config import get_settings
from src.core.logging import get_logger
from src.schemas.responses import ClinicalReport, DiseasePrediction, ImageMetadata

logger = get_logger(__name__)
settings = get_settings()


class ReportGenerator:
    """
    Generate clinical reports from predictions
    """
    
    def __init__(self):
        """Initialize report generator"""
        # Disease descriptions for report
        self.disease_descriptions = {
            "pneumonia": {
                "positive": "Consolidation consistent with pneumonia",
                "anatomical_region": "lung parenchyma",
                "recommendation": "Clinical correlation recommended. Consider follow-up imaging if symptoms persist.",
            },
            "tuberculosis": {
                "positive": "Findings suggestive of tuberculosis",
                "anatomical_region": "lung apices and parenchyma",
                "recommendation": "Immediate clinical correlation required. Recommend sputum culture and AFB smear.",
            },
            "cardiomegaly": {
                "positive": "Enlarged cardiac silhouette suggesting cardiomegaly",
                "anatomical_region": "cardiac silhouette",
                "recommendation": "Consider echocardiography for further evaluation of cardiac size and function.",
            },
            "pleural_effusion": {
                "positive": "Pleural effusion identified",
                "anatomical_region": "pleural space",
                "recommendation": "Consider ultrasound-guided thoracentesis if clinically indicated.",
            },
            "edema": {
                "positive": "Pulmonary edema noted",
                "anatomical_region": "bilateral lung fields",
                "recommendation": "Correlate with clinical symptoms. Consider cardiac evaluation.",
            },
            "fracture": {
                "positive": "Fracture detected",
                "anatomical_region": "bony structures",
                "recommendation": "Orthopedic consultation recommended. Consider CT for detailed assessment.",
            },
        }
        
        logger.info("Report generator initialized")
    
    def generate_report(
        self,
        predictions: Dict[str, DiseasePrediction],
        metadata: ImageMetadata,
    ) -> ClinicalReport:
        """
        Generate clinical report
        
        Args:
            predictions: Disease predictions
            metadata: Image metadata
        
        Returns:
            ClinicalReport object
        """
        # Identify positive findings
        positive_findings = [
            disease for disease, pred in predictions.items()
            if pred.label == "positive"
        ]
        
        # Generate impression
        impression = self._generate_impression(positive_findings, predictions)
        
        # Generate findings
        findings = self._generate_findings(predictions)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(positive_findings, predictions)
        
        # Limitations
        limitations = self._get_limitations()
        
        report = ClinicalReport(
            impression=impression,
            findings=findings,
            recommendations=recommendations,
            limitations=limitations,
        )
        
        logger.debug(
            "Report generated",
            num_positive_findings=len(positive_findings),
            num_findings=len(findings),
        )
        
        return report
    
    def _generate_impression(
        self,
        positive_findings: List[str],
        predictions: Dict[str, DiseasePrediction],
    ) -> str:
        """Generate overall impression"""
        if not positive_findings:
            return "No significant acute findings identified."
        
        if len(positive_findings) == 1:
            disease = positive_findings[0]
            desc = self.disease_descriptions[disease]["positive"]
            return f"Findings suggestive of {disease}. {desc}."
        
        # Multiple findings
        disease_names = ", ".join(positive_findings[:-1]) + f" and {positive_findings[-1]}"
        return f"Multiple findings identified: {disease_names}."
    
    def _generate_findings(
        self,
        predictions: Dict[str, DiseasePrediction],
    ) -> List[str]:
        """Generate detailed findings list"""
        findings = []
        
        for disease, pred in predictions.items():
            if pred.label == "positive":
                desc = self.disease_descriptions[disease]["positive"]
                confidence_pct = int(pred.confidence * 100)
                finding = f"{desc} (confidence: {confidence_pct}%)"
                findings.append(finding)
            elif pred.label == "uncertain":
                confidence_pct = int(pred.confidence * 100)
                finding = f"Equivocal findings for {disease} (confidence: {confidence_pct}%)"
                findings.append(finding)
        
        if not findings:
            findings.append("No acute cardiopulmonary abnormalities detected")
            findings.append("Lungs are clear")
            findings.append("Cardiac silhouette is within normal limits")
            findings.append("No pleural effusion or pneumothorax")
        
        return findings
    
    def _generate_recommendations(
        self,
        positive_findings: List[str],
        predictions: Dict[str, DiseasePrediction],
    ) -> List[str]:
        """Generate clinical recommendations"""
        recommendations = []
        
        # Disease-specific recommendations
        for disease in positive_findings:
            rec = self.disease_descriptions[disease]["recommendation"]
            recommendations.append(rec)
        
        # General recommendations
        if positive_findings:
            recommendations.append("Correlation with clinical history and physical examination is recommended.")
        
        # Critical findings
        critical_diseases = ["tuberculosis"]
        for disease in critical_diseases:
            if disease in positive_findings:
                pred = predictions[disease]
                if pred.confidence > 0.7:
                    recommendations.append(
                        f"CRITICAL: High confidence {disease} detection. Immediate clinical attention required."
                    )
        
        if not recommendations:
            recommendations.append("Routine follow-up as clinically indicated.")
        
        return recommendations
    
    def _get_limitations(self) -> str:
        """Get standard limitations text"""
        return (
            "This is an AI-assisted analysis intended to supplement, not replace, "
            "professional radiological interpretation. Final diagnosis requires "
            "confirmation by a qualified radiologist with full clinical context. "
            "Sensitivity and specificity may vary based on image quality and patient factors."
        )
    
    def generate_structured_findings(
        self,
        predictions: Dict[str, DiseasePrediction],
    ) -> Dict:
        """
        Generate machine-readable structured findings (for HL7 FHIR, etc.)
        
        Args:
            predictions: Disease predictions
        
        Returns:
            Structured findings dictionary
        """
        findings = {
            "summary": {
                "total_findings": sum(1 for p in predictions.values() if p.label == "positive"),
                "critical_findings": sum(
                    1 for disease, p in predictions.items()
                    if p.label == "positive" and disease == "tuberculosis"
                ),
            },
            "diseases": {},
        }
        
        for disease, pred in predictions.items():
            findings["diseases"][disease] = {
                "present": pred.label == "positive",
                "confidence": pred.confidence,
                "probability": pred.probability,
                "clinical_significance": settings.get_disease_config(disease)["clinical_significance"],
            }
        
        return findings
    
    def format_for_hl7_fhir(
        self,
        predictions: Dict[str, DiseasePrediction],
        patient_id: str,
        study_id: str,
    ) -> Dict:
        """
        Format report for HL7 FHIR DiagnosticReport
        
        Args:
            predictions: Disease predictions
            patient_id: Patient identifier
            study_id: Study identifier
        
        Returns:
            FHIR-compatible dictionary (simplified)
        """
        from datetime import datetime
        
        report = {
            "resourceType": "DiagnosticReport",
            "id": study_id,
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                    "code": "RAD",
                    "display": "Radiology"
                }]
            }],
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "36643-5",
                    "display": "Chest X-ray"
                }]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "issued": datetime.utcnow().isoformat(),
            "conclusion": self._generate_impression(
                [d for d, p in predictions.items() if p.label == "positive"],
                predictions
            ),
            "conclusionCode": [
                {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": self._get_snomed_code(disease),
                        "display": disease.replace("_", " ").title()
                    }]
                }
                for disease, pred in predictions.items()
                if pred.label == "positive"
            ]
        }
        
        return report
    
    def _get_snomed_code(self, disease: str) -> str:
        """Get SNOMED CT code for disease (simplified mapping)"""
        snomed_codes = {
            "pneumonia": "233604007",
            "tuberculosis": "56717001",
            "cardiomegaly": "80891009",
            "pleural_effusion": "60046008",
            "edema": "19242006",
            "fracture": "125605004",
        }
        return snomed_codes.get(disease, "unknown")
