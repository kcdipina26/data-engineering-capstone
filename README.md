# LetsCycleToRecycle – E-Waste Tracking Prototype

A full-stack QR-code-based e-waste tracking system that brings transparency to device recycling workflows. Built with Flask, Oracle Database, and Python, this prototype enables seamless tracking from device intake to final recycling.

## Video Demonstration

Watch the full capstone presentation here:  
[LetsCycleToRecycle Project Walkthrough](https://youtu.be/ZqrynrssrJU)

## Overview

LetsCycleToRecycle addresses the growing challenge of electronic waste management by providing a transparent, code-driven approach to tracking devices through their recycling journey. Employees can log devices, generate unique QR codes, and customers can monitor their electronics in real-time as they move through the recycling process.

## Core Features

**Device Management**
- Streamlined intake form for employee data entry
- Automatic QR code generation for each device
- Customer-facing tracking interface for real-time status updates

**Database Architecture**
- Oracle-backed relational database supporting Customer, Device, Order, OrdLine, and Employee tables
- Secure data persistence and query optimization
- Real-time synchronization across all system components

**Global Access**
- ngrok integration enables QR code scanning from anywhere
- No VPN or local network requirements

## Technology Stack

- **Backend**: Python Flask for routing and business logic
- **Database**: Oracle XE with oracledb driver for enterprise-grade data management
- **QR Generation**: qrcode library for creating scannable device identifiers
- **Frontend**: HTML templates styled with Bootstrap for responsive design
- **Tunneling**: ngrok for secure public access during development

## Project Architecture
```
app.py        # Application routes and UI rendering
services.py   # Oracle database queries and QR code generation logic
db.py         # Oracle connection configuration
templates/    # HTML template files
static/       # CSS stylesheets and generated QR code images
```

## Getting Started

1. Activate your virtual environment
2. Launch the application: `python app.py`
3. Start ngrok tunnel: `ngrok http 5000`
4. Scan the generated QR code to begin tracking your device

## Roadmap

**Short Term**
- Cloud deployment via Render for production-ready hosting
- Enhanced web interface with advanced filtering and analytics

**Long Term**
- Native mobile application for iOS and Android
- Integration with third-party recycling facility systems
- Expanded reporting and environmental impact metrics

## Acknowledgments

This project was developed with guidance from Faculty Coach Professor Todd Jones and support from Dr. Yu. Their expertise in database systems and sustainable technology practices was instrumental in bringing this prototype to life.

---

*Contributing to a cleaner planet, one scanned device at a time.*