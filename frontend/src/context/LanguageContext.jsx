import { createContext, useContext, useState, useEffect } from "react";

const translations = {
  en: {
    // Navigation
    "nav.home": "Home",
    "nav.jobs": "Find Jobs",
    "nav.resumes": "My Resume",
    "nav.applications": "Applications",
    "nav.insights": "Insights",
    "nav.profile": "Profile",
    "nav.settings": "Settings",
    "nav.signOut": "Sign Out",
    "nav.more": "More",
    "nav.searchPlaceholder": "Search jobs, skills, companies...",

    // Common Actions
    "action.findJobsForMe": "Find Jobs for Me",
    "action.viewOpportunity": "View Opportunity",
    "action.tailorResume": "Tailor My Resume",
    "action.analyzeResume": "Analyze Resume",
    "action.uploadResume": "Upload Resume",
    "action.downloadPdf": "Download PDF",
    "action.downloadDocx": "Download DOCX",
    "action.reviewResume": "Review Resume",
    "action.updateStatus": "Update Status",
    "action.save": "Save",
    "action.saved": "Saved",
    "action.close": "Close",
    "action.cancel": "Cancel",
    "action.continue": "Continue",
    "action.getStarted": "Get Started Free",
    "action.seeHowItWorks": "See How It Works",
    "action.tryAgain": "Try Again",
    "action.refresh": "Refresh",
    "action.delete": "Delete",
    "action.edit": "Edit",

    // Dashboard
    "dash.greetingMorning": "Good morning",
    "dash.greetingAfternoon": "Good afternoon",
    "dash.greetingEvening": "Good evening",
    "dash.subtitle": "Here's what needs your attention.",
    "dash.nextBestOpportunity": "Your Next Best Opportunity",
    "dash.continueWhereLeftOff": "Continue Where You Left Off",
    "dash.recommendedForYou": "Recommended For You",
    "dash.applicationActivity": "Application Activity",
    "dash.profileReadiness": "Profile Readiness",
    "dash.completeProfile": "Complete Profile",
    "dash.viewAllJobs": "View All Opportunities",

    // Jobs
    "jobs.title": "Find Jobs",
    "jobs.subtitle": "Discover opportunities that fit your skills and career goals.",
    "jobs.recommendedTab": "Recommended for You",
    "jobs.allTab": "All Opportunities",
    "jobs.matchingSkills": "matching skills",
    "jobs.skillsMissing": "skills missing",
    "jobs.match": "Match",
    "jobs.searchPlaceholder": "Search by title, skill, or company...",
    "jobs.filterType": "Job Type",
    "jobs.filterLevel": "Experience",
    "jobs.allTypes": "All Types",
    "jobs.allLevels": "All Levels",
    "jobs.findingOpportunities": "Finding opportunities that fit your profile...",
    "jobs.foundCount": "opportunities found",
    "jobs.seeHowSearched": "See how we searched",
    "jobs.noJobsFound": "No opportunities found",
    "jobs.noJobsDesc": "Try adjusting your filters or click 'Find Jobs for Me' to discover personalized matches.",

    // Job Details & Match
    "jobDetail.overview": "Overview",
    "jobDetail.whatYoullDo": "What You'll Do",
    "jobDetail.requirements": "Requirements",
    "jobDetail.yourFit": "Your Fit",
    "jobDetail.resumeMatch": "Resume Match",
    "jobDetail.applyExternal": "Apply Externally",
    "jobDetail.whyYouMatch": "Why You Match",
    "jobDetail.missingSkills": "Skills to Strengthen",
    "jobDetail.skills": "Skills",
    "jobDetail.projects": "Projects",
    "jobDetail.experience": "Experience",
    "jobDetail.role": "Role Alignment",
    "jobDetail.location": "Location",

    // Resume
    "resume.title": "My Resume",
    "resume.subtitle": "Keep your resumes ready for every opportunity.",
    "resume.yourResumes": "Your Resumes",
    "resume.originalResume": "Original Resume",
    "resume.parsedSuccess": "Parsed successfully",
    "resume.viewInsights": "View Insights",
    "resume.tailoredVersions": "Tailored Versions",
    "resume.dragDrop": "Drag & drop your PDF resume here, or browse files",
    "resume.insightsTitle": "Resume Insights",
    "resume.skillsCount": "Skills",
    "resume.projectsCount": "Projects",
    "resume.expCount": "Experience",
    "resume.eduCount": "Education",

    // Tailoring
    "tailor.title": "AI Resume Tailoring",
    "tailor.step1": "Choose Resume",
    "tailor.step2": "Confirm",
    "tailor.step3": "Tailoring",
    "tailor.step4": "Review",
    "tailor.loadingText": "Tailoring your resume...",
    "tailor.loadingSub": "Optimizing your resume for this role while preserving your actual experience.",
    "tailor.ready": "Your resume is ready",
    "tailor.whatChanged": "What Changed",
    "tailor.relevantKeywords": "Relevant Keywords Highlighted",
    "tailor.notAdded": "Requirements Not Added",
    "tailor.notAddedExpl": "This requirement wasn't added because it wasn't supported by your existing resume.",
    "tailor.trustMessage": "Your original resume is unchanged. CareerPilot only uses information supported by your existing profile.",
    "tailor.compare": "Compare Before & After",
    "tailor.original": "Original",
    "tailor.tailored": "Tailored",

    // Applications
    "app.title": "Applications",
    "app.activeCount": "active applications",
    "app.saved": "Saved",
    "app.applied": "Applied",
    "app.interview": "Interview",
    "app.offer": "Offer",
    "app.rejected": "Rejected",
    "app.nextFollowUp": "Next follow-up",
    "app.viewApp": "View Application",
    "app.noApps": "No applications yet",
    "app.noAppsDesc": "Once you apply to a job, you can track its progress and milestones here.",

    // Insights / Analytics
    "insights.title": "Career Insights",
    "insights.subtitle": "Meaningful trends and actionable patterns across your job search.",
    "insights.funnel": "Application Funnel",
    "insights.matchDistribution": "Match Score Distribution",
    "insights.missingSkills": "Most Common Missing Skills",
    "insights.strengths": "Role Fit & Domain Strengths",

    // Settings
    "settings.title": "Settings & Preferences",
    "settings.account": "Account",
    "settings.appearance": "Appearance",
    "settings.language": "Language",
    "settings.accessibility": "Accessibility",
    "settings.notifications": "Notifications",
    "settings.privacy": "Privacy & Data",
    "settings.dangerZone": "Danger Zone",
    "settings.themeLight": "Light",
    "settings.themeDark": "Dark",
    "settings.themeSystem": "System",
    "settings.textSize": "Text Size",
    "settings.sizeSmall": "Small",
    "settings.sizeDefault": "Default",
    "settings.sizeLarge": "Large",
    "settings.sizeExtraLarge": "Extra Large",
    "settings.highContrast": "High Contrast",
    "settings.reducedMotion": "Reduce Motion",
  },
  hi: {
    // Navigation
    "nav.home": "होम",
    "nav.jobs": "नौकरियां खोजें",
    "nav.resumes": "मेरा रिज्यूमे",
    "nav.applications": "आवेदन",
    "nav.insights": "इनसाइट्स",
    "nav.profile": "प्रोफ़ाइल",
    "nav.settings": "सेटिंग्स",
    "nav.signOut": "साइन आउट",
    "nav.more": "अधिक",
    "nav.searchPlaceholder": "नौकरियां, कौशल, कंपनियां खोजें...",

    // Common Actions
    "action.findJobsForMe": "मेरे लिए उपयुक्त नौकरियां खोजें",
    "action.viewOpportunity": "अवसर देखें",
    "action.tailorResume": "रिज्यूमे अनुकूलित करें",
    "action.analyzeResume": "रिज्यूमे विश्लेषण करें",
    "action.uploadResume": "रिज्यूमे अपलोड करें",
    "action.downloadPdf": "PDF डाउनलोड करें",
    "action.downloadDocx": "DOCX डाउनलोड करें",
    "action.reviewResume": "रिज्यूमे की समीक्षा करें",
    "action.updateStatus": "स्थिति अपडेट करें",
    "action.save": "सुरक्षित करें",
    "action.saved": "सुरक्षित",
    "action.close": "बंद करें",
    "action.cancel": "रद्द करें",
    "action.continue": "जारी रखें",
    "action.getStarted": "मुफ़्त शुरू करें",
    "action.seeHowItWorks": "कार्यप्रणाली देखें",
    "action.tryAgain": "पुनः प्रयास करें",
    "action.refresh": "रिफ्रेश",
    "action.delete": "हटाएं",
    "action.edit": "संपादित करें",

    // Dashboard
    "dash.greetingMorning": "शुभ प्रभात",
    "dash.greetingAfternoon": "शुभ दोपहर",
    "dash.greetingEvening": "शुभ संध्या",
    "dash.subtitle": "यहाँ वह सब है जिस पर आपका ध्यान आवश्यक है।",
    "dash.nextBestOpportunity": "आपका अगला सर्वश्रेष्ठ अवसर",
    "dash.continueWhereLeftOff": "जहाँ छोड़ा था वहाँ से जारी रखें",
    "dash.recommendedForYou": "आपके लिए अनुशंसित",
    "dash.applicationActivity": "आवेदन गतिविधि",
    "dash.profileReadiness": "प्रोफ़ाइल तत्परता",
    "dash.completeProfile": "प्रोफ़ाइल पूर्ण करें",
    "dash.viewAllJobs": "सभी अवसर देखें",

    // Jobs
    "jobs.title": "नौकरियां खोजें",
    "jobs.subtitle": "अपने कौशल और लक्ष्यों के अनुसार अवसर खोजें।",
    "jobs.recommendedTab": "आपके लिए अनुशंसित",
    "jobs.allTab": "सभी अवसर",
    "jobs.matchingSkills": "मेल खाते कौशल",
    "jobs.skillsMissing": "अपेक्षित कौशल शेष",
    "jobs.match": "मैच",
    "jobs.searchPlaceholder": "पद, कौशल या कंपनी द्वारा खोजें...",
    "jobs.filterType": "कार्य प्रकार",
    "jobs.filterLevel": "अनुभव स्तर",
    "jobs.allTypes": "सभी प्रकार",
    "jobs.allLevels": "सभी स्तर",
    "jobs.findingOpportunities": "आपकी प्रोफ़ाइल के अनुसार अवसर खोजे जा रहे हैं...",
    "jobs.foundCount": "अवसर मिले",
    "jobs.seeHowSearched": "खोज विवरण देखें",
    "jobs.noJobsFound": "कोई अवसर नहीं मिला",
    "jobs.noJobsDesc": "फ़िल्टर बदलें या 'मेरे लिए उपयुक्त नौकरियां खोजें' पर क्लिक करें।",

    // Job Details & Match
    "jobDetail.overview": "विवरण",
    "jobDetail.whatYoullDo": "कार्य दायित्व",
    "jobDetail.requirements": "आवश्यकताएं",
    "jobDetail.yourFit": "आपकी उपयुक्तता",
    "jobDetail.resumeMatch": "रिज्यूमे मैच",
    "jobDetail.applyExternal": "कंपनी साइट पर आवेदन करें",
    "jobDetail.whyYouMatch": "आप क्यों उपयुक्त हैं",
    "jobDetail.missingSkills": "सुधार योग्य कौशल",
    "jobDetail.skills": "कौशल",
    "jobDetail.projects": "प्रोजेक्ट्स",
    "jobDetail.experience": "अनुभव",
    "jobDetail.role": "पद अनुरूपता",
    "jobDetail.location": "स्थान",

    // Resume
    "resume.title": "मेरा रिज्यूमे",
    "resume.subtitle": "हर अवसर के लिए अपना रिज्यूमे तैयार रखें।",
    "resume.yourResumes": "आपके रिज्यूमे",
    "resume.originalResume": "मूल रिज्यूमे",
    "resume.parsedSuccess": "सफलतापूर्वक विश्लेषित",
    "resume.viewInsights": "इनसाइट्स देखें",
    "resume.tailoredVersions": "अनुकूलित संस्करण",
    "resume.dragDrop": "अपनी PDF फ़ाइल यहाँ खींचें या ब्राउज़ करें",
    "resume.insightsTitle": "रिज्यूमे इनसाइट्स",
    "resume.skillsCount": "कौशल",
    "resume.projectsCount": "प्रोजेक्ट्स",
    "resume.expCount": "अनुभव",
    "resume.eduCount": "शिक्षा",

    // Tailoring
    "tailor.title": "रिज्यूमे अनुकूलन",
    "tailor.step1": "रिज्यूमे चुनें",
    "tailor.step2": "पुष्टि करें",
    "tailor.step3": "अनुकूलन जारी",
    "tailor.step4": "समीक्षा",
    "tailor.loadingText": "रिज्यूमे अनुकूलित किया जा रहा है...",
    "tailor.loadingSub": "आपके वास्तविक अनुभव को सुरक्षित रखते हुए इस पद के लिए अनुकूलन।",
    "tailor.ready": "आपका रिज्यूमे तैयार है",
    "tailor.whatChanged": "क्या बदलाव किए गए",
    "tailor.relevantKeywords": "प्रमुख कीवर्ड्स शामिल किए गए",
    "tailor.notAdded": "शामिल न की गई आवश्यकताएं",
    "tailor.notAddedExpl": "यह आवश्यकता आपके मूल रिज्यूमे में नहीं मिलने के कारण नहीं जोड़ी गई।",
    "tailor.trustMessage": "आपका मूल रिज्यूमे अपरिवर्तित है। केवल प्रमाणित जानकारी का उपयोग होता है।",
    "tailor.compare": "पहले और बाद की तुलना",
    "tailor.original": "मूल",
    "tailor.tailored": "अनुकूलित",

    // Applications
    "app.title": "आवेदन",
    "app.activeCount": "सक्रिय आवेदन",
    "app.saved": "सुरक्षित",
    "app.applied": "आवेदन किया",
    "app.interview": "साक्षात्कार",
    "app.offer": "ऑफर मिला",
    "app.rejected": "अस्वीकृत",
    "app.nextFollowUp": "अगला फॉलो-अप",
    "app.viewApp": "आवेदन देखें",
    "app.noApps": "अभी कोई आवेदन नहीं है",
    "app.noAppsDesc": "जब आप आवेदन करेंगे, तो उसकी प्रगति यहाँ ट्रैक की जा सकती है।",

    // Insights
    "insights.title": "करियर इनसाइट्स",
    "insights.subtitle": "आपकी नौकरी खोज के महत्वपूर्ण रुझान और आंकड़े।",
    "insights.funnel": "आवेदन फनल",
    "insights.matchDistribution": "मैच स्कोर वितरण",
    "insights.missingSkills": "अपेक्षित मुख्य कौशल",
    "insights.strengths": "पद उपयुक्तता और शक्तियां",

    // Settings
    "settings.title": "सेटिंग्स और प्राथमिकताएं",
    "settings.account": "खाता",
    "settings.appearance": "थीम",
    "settings.language": "भाषा",
    "settings.accessibility": "पहुंचयोग्यता",
    "settings.notifications": "सूचनाएं",
    "settings.privacy": "गोपनीयता",
    "settings.dangerZone": "अकाउंट प्रबंधन",
    "settings.themeLight": "लाइट",
    "settings.themeDark": "डार्क",
    "settings.themeSystem": "सिस्टम",
    "settings.textSize": "टेक्स्ट का आकार",
    "settings.sizeSmall": "छोटा",
    "settings.sizeDefault": "मानक",
    "settings.sizeLarge": "बड़ा",
    "settings.sizeExtraLarge": "अति बड़ा",
    "settings.highContrast": "उच्च कंट्रास्ट",
    "settings.reducedMotion": "कम मोशन",
  },
  mr: {
    // Navigation
    "nav.home": "मुख्यपृष्ठ",
    "nav.jobs": "नोकऱ्या शोधा",
    "nav.resumes": "माझा रेझ्युमे",
    "nav.applications": "माझे अर्ज",
    "nav.insights": "इनसाइट्स",
    "nav.profile": "माझी प्रोफाइल",
    "nav.settings": "सेटिंग्ज",
    "nav.signOut": "साइन आउट",
    "nav.more": "अधिक",
    "nav.searchPlaceholder": "नोकऱ्या, कौशल्ये, कंपन्या शोधा...",

    // Common Actions
    "action.findJobsForMe": "माझ्यासाठी नोकऱ्या शोधा",
    "action.viewOpportunity": "संधी पहा",
    "action.tailorResume": "रेझ्युमे अनुकूलित करा",
    "action.analyzeResume": "रेझ्युमे विश्लेषण",
    "action.uploadResume": "रेझ्युमे अपलोड करा",
    "action.downloadPdf": "PDF डाउनलोड करा",
    "action.downloadDocx": "DOCX डाउनलोड करा",
    "action.reviewResume": "रेझ्युमे तपासा",
    "action.updateStatus": "स्थिती बदला",
    "action.save": "जतन करा",
    "action.saved": "जतन केले",
    "action.close": "बंद करा",
    "action.cancel": "रद्द करा",
    "action.continue": "पुढे जा",
    "action.getStarted": "मोफत सुरू करा",
    "action.seeHowItWorks": "कसे कार्य करते पहा",
    "action.tryAgain": "पुन्हा प्रयत्न करा",
    "action.refresh": "रिफ्रेश",
    "action.delete": "हटवा",
    "action.edit": "संपादित करा",

    // Dashboard
    "dash.greetingMorning": "शुभ सकाळ",
    "dash.greetingAfternoon": "शुभ दुपार",
    "dash.greetingEvening": "शुभ संध्याकाळ",
    "dash.subtitle": "येथे आपल्यासाठी महत्त्वाच्या बाबी आहेत.",
    "dash.nextBestOpportunity": "आपली पुढील सर्वोत्तम संधी",
    "dash.continueWhereLeftOff": "जिथे थांबलात तिथून पुढे सुरू करा",
    "dash.recommendedForYou": "तुमच्यासाठी शिफारस केलेले",
    "dash.applicationActivity": "अर्ज स्थिती",
    "dash.profileReadiness": "प्रोफाइल पूर्णता",
    "dash.completeProfile": "प्रोफाइल पूर्ण करा",
    "dash.viewAllJobs": "सर्व संधी पहा",

    // Jobs
    "jobs.title": "नोकऱ्या शोधा",
    "jobs.subtitle": "आपल्या कौशल्यानुसार सर्वोत्तम संधी शोधा.",
    "jobs.recommendedTab": "तुमच्यासाठी शिफारस केलेले",
    "jobs.allTab": "सर्व संधी",
    "jobs.matchingSkills": "जुळणारी कौशल्ये",
    "jobs.skillsMissing": "अपेक्षित कौशल्ये बाकी",
    "jobs.match": "मॅच",
    "jobs.searchPlaceholder": "पद, कौशल्ये किंवा कंपनीद्वारे शोधा...",
    "jobs.filterType": "कामाचा प्रकार",
    "jobs.filterLevel": "अनुभव स्तर",
    "jobs.allTypes": "सर्व प्रकार",
    "jobs.allLevels": "सर्व स्तर",
    "jobs.findingOpportunities": "तुमच्या प्रोफाइलनुसार नोकऱ्या शोधत आहोत...",
    "jobs.foundCount": "संधी सापडल्या",
    "jobs.seeHowSearched": "शोध तपशील पहा",
    "jobs.noJobsFound": "कोणतीही संधी सापडली नाही",
    "jobs.noJobsDesc": "फिल्टर बदला किंवा 'माझ्यासाठी नोकऱ्या शोधा' वर क्लिक करा.",

    // Job Details & Match
    "jobDetail.overview": "माहिती",
    "jobDetail.whatYoullDo": "कामाचे स्वरूप",
    "jobDetail.requirements": "पात्रता व अटी",
    "jobDetail.yourFit": "तुमची पात्रता",
    "jobDetail.resumeMatch": "रेझ्युमे मॅच",
    "jobDetail.applyExternal": "कंपनीच्या संकेतस्थळावर अर्ज करा",
    "jobDetail.whyYouMatch": "तुम्ही का पात्र आहात",
    "jobDetail.missingSkills": "सुधारणेची गरज असलेली कौशल्ये",
    "jobDetail.skills": "कौशल्ये",
    "jobDetail.projects": "प्रकल्प",
    "jobDetail.experience": "अनुभव",
    "jobDetail.role": "पदाची अनुरूपता",
    "jobDetail.location": "ठिकाण",

    // Resume
    "resume.title": "माझा रेझ्युमे",
    "resume.subtitle": "प्रत्येक संधीसाठी रेझ्युमे सज्ज ठेवा.",
    "resume.yourResumes": "तुमचे रेझ्युमे",
    "resume.originalResume": "मूळ रेझ्युमे",
    "resume.parsedSuccess": "यशस्वीरित्या विश्लेषित",
    "resume.viewInsights": "इनसाइट्स पहा",
    "resume.tailoredVersions": "अनुकूलित आवृत्त्या",
    "resume.dragDrop": "तुमची PDF फाइल येथे टाका किंवा निवडा",
    "resume.insightsTitle": "रेझ्युमे इनसाइट्स",
    "resume.skillsCount": "कौशल्ये",
    "resume.projectsCount": "प्रकल्प",
    "resume.expCount": "अनुभव",
    "resume.eduCount": "शिक्षण",

    // Tailoring
    "tailor.title": "रेझ्युमे अनुकूलन",
    "tailor.step1": "रेझ्युमे निवडा",
    "tailor.step2": "खात्री करा",
    "tailor.step3": "अनुकूलन सुरू",
    "tailor.step4": "तपासा",
    "tailor.loadingText": "रेझ्युमे अनुकूलित केला जात आहे...",
    "tailor.loadingSub": "तुमचा मूळ अनुभव जपून या पदासाठी रेझ्युमे तयार केला जात आहे.",
    "tailor.ready": "तुमचा रेझ्युमे तयार आहे",
    "tailor.whatChanged": "केलेले बदल",
    "tailor.relevantKeywords": "समाविष्ट केलेले कीवर्ड्स",
    "tailor.notAdded": "समाविष्ट न केलेल्या बाबी",
    "tailor.notAddedExpl": "ही माहिती मूळ रेझ्युमेमध्ये नसल्याने जोडलेली नाही.",
    "tailor.trustMessage": "तुमचा मूळ रेझ्युमे सुरक्षित आहे. केवळ सत्य माहिती वापरली जाते.",
    "tailor.compare": "आधी आणि नंतरची तुलना",
    "tailor.original": "मूळ",
    "tailor.tailored": "अनुकूलित",

    // Applications
    "app.title": "माझे अर्ज",
    "app.activeCount": "सक्रिय अर्ज",
    "app.saved": "जतन केलेले",
    "app.applied": "अर्ज पाठवला",
    "app.interview": "मुलाखत",
    "app.offer": "ऑफर मिळाली",
    "app.rejected": "नाकारले",
    "app.nextFollowUp": "पुढील फॉलो-अप",
    "app.viewApp": "अर्ज पहा",
    "app.noApps": "अद्याप कोणताही अर्ज नाही",
    "app.noAppsDesc": "नोकरीसाठी अर्ज केल्यानंतर त्याची प्रगती येथे ट्रॅक करू शकता.",

    // Insights
    "insights.title": "करिअर इनसाइट्स",
    "insights.subtitle": "तुमच्या नोकरी शोधाचे महत्त्वाचे विश्लेषण.",
    "insights.funnel": "अर्ज प्रगती फनेल",
    "insights.matchDistribution": "मॅच स्कोअर वितरण",
    "insights.missingSkills": "आवश्यक असलेली प्रमुख कौशल्ये",
    "insights.strengths": "पदांची उपयुक्तता व सामर्थ्य",

    // Settings
    "settings.title": "सेटिंग्ज आणि प्राधान्ये",
    "settings.account": "खाते",
    "settings.appearance": "थीम",
    "settings.language": "भाषा",
    "settings.accessibility": "अ‍ॅक्सेसिबिलिटी",
    "settings.notifications": "सूचना",
    "settings.privacy": "गोपनीयता",
    "settings.dangerZone": "खाते व्यवस्थापन",
    "settings.themeLight": "लाइट",
    "settings.themeDark": "डार्क",
    "settings.themeSystem": "सिस्टम",
    "settings.textSize": "मजकुराचा आकार",
    "settings.sizeSmall": "लहान",
    "settings.sizeDefault": "सर्वसाधारण",
    "settings.sizeLarge": "मोठा",
    "settings.sizeExtraLarge": "अति मोठा",
    "settings.highContrast": "हाय कॉन्ट्रास्ट",
    "settings.reducedMotion": "मोशन कमी करा",
  },
};

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    return localStorage.getItem("cp_language") || "en";
  });

  useEffect(() => {
    document.documentElement.setAttribute("lang", language);
    localStorage.setItem("cp_language", language);
  }, [language]);

  const setLanguage = (lang) => {
    if (translations[lang]) {
      setLanguageState(lang);
    }
  };

  const t = (key, fallback) => {
    const dict = translations[language] || translations.en;
    if (dict && dict[key] !== undefined) {
      return dict[key];
    }
    const enDict = translations.en;
    if (enDict && enDict[key] !== undefined) {
      return enDict[key];
    }
    return fallback !== undefined ? fallback : key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, languages: ["en", "hi", "mr"] }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useTranslation must be used within a LanguageProvider");
  }
  return ctx;
}
