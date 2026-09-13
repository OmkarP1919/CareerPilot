import React, { useState, useRef, useEffect } from "react";
import { Search, Plus } from "lucide-react";
import { SKILL_SUGGESTIONS } from "./skillSuggestions";

export default function SkillAutocomplete({ onAddSkill, disabled, profileSkills }) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter suggestions
  const normalizedInput = inputValue.trim().toLowerCase();

  // Existing skills (case-insensitive)
  const existingSkills = new Set(
    (profileSkills || []).map(s => (s.skill_name || "").trim().toLowerCase())
  );

  const filteredSuggestions = SKILL_SUGGESTIONS.filter((skill) => {
    // If it's already in the user's profile, don't suggest it
    if (existingSkills.has(skill.name.toLowerCase())) return false;
    // Empty input shows all (up to a limit if we wanted, but we'll show all un-added ones or a slice)
    if (!normalizedInput) return true;
    return skill.name.toLowerCase().includes(normalizedInput);
  }).slice(0, 50); // limit to keep UI snappy

  // Determine if the exact typed skill exists in suggestions
  const exactMatchExists = filteredSuggestions.some(
    (s) => s.name.toLowerCase() === normalizedInput
  );

  // Determine if the exact typed skill is already in profile
  const isAlreadyAdded = existingSkills.has(normalizedInput);

  const handleSelect = (skillName) => {
    if (!skillName.trim() || isAlreadyAdded) return;
    onAddSkill(skillName.trim());
    setInputValue("");
    setIsOpen(false);
    setActiveIndex(-1);
    if (inputRef.current) inputRef.current.focus();
  };

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    const maxIndex = filteredSuggestions.length + (normalizedInput && !exactMatchExists && !isAlreadyAdded ? 1 : 0) - 1;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((prev) => (prev < maxIndex ? prev + 1 : 0));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : maxIndex));
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < filteredSuggestions.length) {
          handleSelect(filteredSuggestions[activeIndex].name);
        } else if (activeIndex === filteredSuggestions.length) {
          // Custom add
          handleSelect(inputValue);
        } else if (normalizedInput && !isAlreadyAdded) {
          handleSelect(inputValue);
        }
        break;
      case "Escape":
        e.preventDefault();
        setIsOpen(false);
        setActiveIndex(-1);
        break;
      default:
        break;
    }
  };

  // Reset active index when input changes
  useEffect(() => {
    setActiveIndex(-1);
    if (inputValue.trim()) {
      setIsOpen(true);
    }
  }, [inputValue]);

  return (
    <div className="skill-autocomplete-container" ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (normalizedInput && !isAlreadyAdded) {
            handleSelect(inputValue);
          }
        }}
        className="profile-quick-skill-form"
        style={{ display: "flex", gap: "var(--space-2)", width: "100%" }}
      >
        <div className="skill-autocomplete-input-wrap" style={{ position: "relative", flex: "1" }}>
          <div style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)", pointerEvents: "none" }}>
            <Search size={16} />
          </div>
          <input
            ref={inputRef}
            type="text"
            className="form-input profile-quick-skill-input"
            style={{ paddingLeft: "36px", width: "100%" }}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder="Search or type a skill..."
            disabled={disabled}
            aria-label="Add a skill"
            aria-expanded={isOpen}
            aria-haspopup="listbox"
            role="combobox"
            aria-controls="skill-suggestions-list"
            aria-activedescendant={activeIndex >= 0 ? `skill-option-${activeIndex}` : undefined}
          />
        </div>
        <button
          type="submit"
          className="btn btn-primary btn-sm profile-quick-skill-btn"
          disabled={disabled || !normalizedInput || isAlreadyAdded}
          style={{ minWidth: "80px", height: "44px" }}
        >
          <Plus size={16} aria-hidden="true" />
          <span>Add</span>
        </button>
      </form>

      {isOpen && (filteredSuggestions.length > 0 || (normalizedInput && !exactMatchExists && !isAlreadyAdded)) && (
        <ul
          id="skill-suggestions-list"
          className="skill-autocomplete-dropdown"
          role="listbox"
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-md)",
            maxHeight: "240px",
            overflowY: "auto",
            zIndex: 100,
            padding: "var(--space-1) 0",
            listStyle: "none",
            margin: "4px 0 0 0"
          }}
        >
          {filteredSuggestions.map((skill, index) => {
            const isActive = index === activeIndex;
            return (
              <li
                key={skill.name}
                id={`skill-option-${index}`}
                role="option"
                aria-selected={isActive}
                onClick={() => handleSelect(skill.name)}
                onMouseEnter={() => setActiveIndex(index)}
                style={{
                  padding: "var(--space-2) var(--space-3)",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  backgroundColor: isActive ? "var(--bg-surface-hover)" : "transparent",
                  color: "var(--text-primary)",
                  minHeight: "44px"
                }}
              >
                <span style={{ fontWeight: 500 }}>{skill.name}</span>
                <span style={{ fontSize: "12px", color: "var(--text-secondary)", paddingLeft: "8px" }}>
                  {skill.category}
                </span>
              </li>
            );
          })}

          {normalizedInput && !exactMatchExists && !isAlreadyAdded && (
            <li
              id={`skill-option-${filteredSuggestions.length}`}
              role="option"
              aria-selected={activeIndex === filteredSuggestions.length}
              onClick={() => handleSelect(inputValue)}
              onMouseEnter={() => setActiveIndex(filteredSuggestions.length)}
              style={{
                padding: "var(--space-2) var(--space-3)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                backgroundColor: activeIndex === filteredSuggestions.length ? "var(--bg-surface-hover)" : "transparent",
                color: "var(--accent)",
                borderTop: filteredSuggestions.length > 0 ? "1px solid var(--border)" : "none",
                minHeight: "44px"
              }}
            >
              <Plus size={14} />
              <span>Add <strong style={{ fontWeight: 600 }}>"{inputValue.trim()}"</strong></span>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
