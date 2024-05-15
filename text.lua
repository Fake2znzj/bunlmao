
local Players = game:GetService("Players")
local LocalPlayer = Players.LocalPlayer
local Character = LocalPlayer.Character or LocalPlayer.CharacterAdded:Wait()
local Humanoid = Character:WaitForChild("Humanoid")
local HumanoidRootPart = Character:WaitForChild("HumanoidRootPart")

local function findNearestMob()
    local nearestMob = nil
    local nearestDistance = math.huge
    for _, mob in pairs(workspace.Mobs:GetChildren()) do
        if mob:FindFirstChild("Humanoid") and mob.Humanoid.Health > 0 then
            local distance = (HumanoidRootPart.Position - mob.HumanoidRootPart.Position).Magnitude
            if distance < nearestDistance then
                nearestMob = mob
                nearestDistance = distance
            end
        end
    end
    return nearestMob
end

local function findNearestFruit()
    local nearestFruit = nil
    local nearestDistance = math.huge
    for _, fruit in pairs(workspace.Fruits:GetChildren()) do
        local distance = (HumanoidRootPart.Position - fruit.Position).Magnitude
        if distance < nearestDistance then
            nearestFruit = fruit
            nearestDistance = distance
        end
    end
    return nearestFruit
end

while true do
    local mob = findNearestMob()
    local fruit = findNearestFruit()

    if mob then
        Humanoid:MoveTo(mob.HumanoidRootPart.Position)
        Humanoid.Jump = true
        wait(0.5)
        game:GetService("ReplicatedStorage").Remotes.Damage:FireServer(mob)
    elseif fruit then
        Humanoid:MoveTo(fruit.Position)
        wait(0.5)
        fireproximityprompt(fruit.ProximityPrompt)
    end

    wait(0.1)
end
