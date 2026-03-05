import os

from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import (
	ScrapeWebsiteTool
)
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_repo_search_tool import GitLabRepoSearchTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_file_tree_tool import GitLabFileTreeTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_file_reader import GitLabFileReadTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_issue_list_tool import GitLabIssueListTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_mr_list_tool import GitLabMRListTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_list_group_projects import GitLabListGroupProjectsTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_search import GitLabSearchTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_repo_tree_lister import GitLabRepoTreeListerTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_get_file import GitLabGetFileTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_list_merge_requests import GitLabListMergeRequestsTool
from ai_pre_refinement_engine___evidence_based_quality_assurance.tools.gitlab_list_issues import GitLabListIssuesTool




@CrewBase
class AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew:
    """AiPreRefinementEngineEvidenceBasedQualityAssurance crew"""

    
    @agent
    def planner_and_orchestrator(self) -> Agent:
        
        return Agent(
            config=self.agents_config["planner_and_orchestrator"],
            
            
            tools=[				GitLabRepoSearchTool(),
				ScrapeWebsiteTool(),
				GitLabSearchTool(),
				GitLabListGroupProjectsTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
            ),

        )

    @agent
    def repository_scout(self) -> Agent:
        
        return Agent(
            config=self.agents_config["repository_scout"],
            
            
            tools=[				GitLabFileTreeTool(),
				GitLabFileReadTool(),
				GitLabIssueListTool(),
				GitLabMRListTool(),
				ScrapeWebsiteTool(),
				GitLabListGroupProjectsTool(),
				GitLabSearchTool(),
				GitLabRepoTreeListerTool(),
				GitLabGetFileTool(),
				GitLabListMergeRequestsTool(),
				GitLabListIssuesTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.1,
            ),

        )

    @agent
    def synthesis_tech_lead(self) -> Agent:
        
        return Agent(
            config=self.agents_config["synthesis_tech_lead"],
            tools=[GitLabFileReadTool(), GitLabGetFileTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
            ),

        )

    @agent
    def product_optimizer(self) -> Agent:
        
        return Agent(
            config=self.agents_config["product_optimizer"],
            tools=[GitLabFileReadTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.4,
            ),

        )

    @agent
    def quality_gate_critic(self) -> Agent:
        
        return Agent(
            config=self.agents_config["quality_gate_critic"],
            tools=[GitLabFileReadTool(), GitLabGetFileTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
            ),

        )

    @agent
    def cache_intelligence_manager(self) -> Agent:
        
        return Agent(
            config=self.agents_config["cache_intelligence_manager"],
            tools=[],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.2,
            ),

        )

    @agent
    def complexity_assessment_specialist(self) -> Agent:
        
        return Agent(
            config=self.agents_config["complexity_assessment_specialist"],
            tools=[GitLabFileReadTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
            ),

        )


    
    @task
    def input_normalization_and_gitlab_scope_validation(self) -> Task:
        return Task(
            config=self.tasks_config["input_normalization_and_gitlab_scope_validation"],
            markdown=False,
            
            
        )
    
    @task
    def gitlab_tools_self_test(self) -> Task:
        return Task(
            config=self.tasks_config["gitlab_tools_self_test"],
            markdown=False,
            
            
        )
    
    @task
    def repository_inventory_and_candidate_selection(self) -> Task:
        return Task(
            config=self.tasks_config["repository_inventory_and_candidate_selection"],
            markdown=False,
            
            
        )
    
    @task
    def two_pass_evidence_retrieval(self) -> Task:
        return Task(
            config=self.tasks_config["two_pass_evidence_retrieval"],
            markdown=False,
            
            
        )
    
    @task
    def evidence_gate_fail_or_escalate(self) -> Task:
        return Task(
            config=self.tasks_config["evidence_gate_fail_or_escalate"],
            markdown=False,
            
            
        )
    
    @task
    def mr_issue_similarity_mining(self) -> Task:
        return Task(
            config=self.tasks_config["mr_issue_similarity_mining"],
            markdown=False,
            
            
        )
    
    @task
    def plan_large_scale_repository_strategy(self) -> Task:
        return Task(
            config=self.tasks_config["plan_large_scale_repository_strategy"],
            markdown=False,
            
            
        )
    
    @task
    def execute_two_pass_analysis_with_intelligent_stopping(self) -> Task:
        return Task(
            config=self.tasks_config["execute_two_pass_analysis_with_intelligent_stopping"],
            markdown=False,
            
            
        )
    
    @task
    def bootstrap_repository_system_map(self) -> Task:
        return Task(
            config=self.tasks_config["bootstrap_repository_system_map"],
            markdown=False,
            
            
        )
    
    @task
    def define_evidence_sufficiency_and_stop_conditions(self) -> Task:
        return Task(
            config=self.tasks_config["define_evidence_sufficiency_and_stop_conditions"],
            markdown=False,
            
            
        )
    
    @task
    def create_repo_summary_index_cache(self) -> Task:
        return Task(
            config=self.tasks_config["create_repo_summary_index_cache"],
            markdown=False,
            
            
        )
    
    @task
    def validate_cache_quality_and_completeness(self) -> Task:
        return Task(
            config=self.tasks_config["validate_cache_quality_and_completeness"],
            markdown=False,
            
            
        )
    
    @task
    def evidence_gate_validation(self) -> Task:
        return Task(
            config=self.tasks_config["evidence_gate_validation"],
            markdown=False,
            
            
        )
    
    @task
    def synthesis_tech_lead_evidence_based_hypothesis_and_complexity(self) -> Task:
        return Task(
            config=self.tasks_config["synthesis_tech_lead_evidence_based_hypothesis_and_complexity"],
            markdown=False,
            
            
        )
    
    @task
    def execute_systematic_complexity_assessment(self) -> Task:
        return Task(
            config=self.tasks_config["execute_systematic_complexity_assessment"],
            markdown=False,
            
            
        )
    
    @task
    def generate_product_implementation_variants(self) -> Task:
        return Task(
            config=self.tasks_config["generate_product_implementation_variants"],
            markdown=False,
            
            
        )
    
    @task
    def quality_gate_citations_assumption_detection(self) -> Task:
        return Task(
            config=self.tasks_config["quality_gate_citations_assumption_detection"],
            markdown=False,
            
            
        )
    
    @task
    def generate_discovery_action_plan(self) -> Task:
        return Task(
            config=self.tasks_config["generate_discovery_action_plan"],
            markdown=False,
            
            
        )
    
    @task
    def generate_comprehensive_final_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_comprehensive_final_report"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the AiPreRefinementEngineEvidenceBasedQualityAssurance crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            chat_llm=LLM(model="openai/gpt-4o-mini"),
        )


