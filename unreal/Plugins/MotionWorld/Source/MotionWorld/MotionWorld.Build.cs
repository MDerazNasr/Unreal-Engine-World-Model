using UnrealBuildTool;

public class MotionWorld : ModuleRules
{
    public MotionWorld(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.Add("Core");

        PrivateDependencyModuleNames.AddRange(
            new[]
            {
                "CoreUObject",
                "Engine",
                "Json",
                "Mover"
            }
        );
    }
}
